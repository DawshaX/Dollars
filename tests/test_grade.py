"""اختبارات طقم الجودة السينمائية — لازم يحسّن الصورة فعلًا مش يبوّظها."""
import numpy as np
import pytest

from engine import grade


@pytest.fixture
def img():
    rng = np.random.default_rng(3)
    h, w = 90, 160
    base = np.zeros((h, w, 3), np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base[:, :, 0] = 0.05 + 0.35 * (xx / w)
    base[:, :, 1] = 0.05 + 0.25 * (yy / h)
    base[:, :, 2] = 0.10 + 0.20 * ((xx + yy) / (w + h))
    base += rng.normal(0, 0.01, base.shape).astype(np.float32)
    base[20:40, 100:120] = 1.0          # ضوء ساطع (للبloom/الهالة)
    return np.clip(base, 0, 1)


def test_grades_keep_range_and_increase_contrast(img):
    for preset in grade.GRADES:
        out = grade.apply(img, preset=preset)
        assert out.shape == img.shape and out.dtype == np.float32
        assert 0.0 <= out.min() and out.max() <= 1.0
    a = grade.quality_report((img * 255).astype(np.uint8))
    b = grade.quality_report((grade.apply(img, preset="cinema_night") * 255).astype(np.uint8))
    # الـtonemap بيلمّ الأنوار المحروقة (ده المطلوب) ⇒ التباين ممكن يهدى شوية مش ينهار
    assert b["contrast"] >= a["contrast"] * 0.85
    assert b["saturation"] > a["saturation"]            # بقى أغنى لونيًا
    assert b["sharpness"] > a["sharpness"]              # تفاصيل أوضح
    assert b["white_clip"] <= a["white_clip"]           # استرجاع المنطقة المحروقة


def test_bloom_and_halation_spread_light(img):
    b = grade.bloom(img, threshold=0.7, strength=0.8, radius=20)
    assert b.mean() > img.mean()
    around = b[45:55, 105:115].mean()                   # حوالين الضوء الساطع
    assert around > img[45:55, 105:115].mean()          # الهالة وصلت للمنطقة المحيطة
    h = grade.halation(img, threshold=0.7, strength=0.6)
    assert h[:, :, 0].mean() > h[:, :, 2].mean()        # الهالة حمراء أكتر من الأزرق


def test_dof_blurs_off_focus_keeps_focus_sharp(img):
    h, w = img.shape[:2]
    depth = np.zeros((h, w), np.float32)
    depth[:, : w // 2] = 0.72                            # النص الأول في مستوى التركيز
    depth[:, w // 2:] = 0.0                              # النص التاني قريب جدًا ⇒ بوكيه
    out = grade.dof(img, depth, focus=0.72, aperture=0.25, max_blur=6)
    sharp_in = grade.quality_report((out[:, :w // 2] * 255).astype(np.uint8))["sharpness"]
    sharp_out = grade.quality_report((out[:, w // 2:] * 255).astype(np.uint8))["sharpness"]
    assert sharp_in > sharp_out


def test_god_rays_only_with_bright_source(img):
    dark = np.zeros_like(img)
    assert np.allclose(grade.god_rays(dark, strength=0.5), dark)
    rays = grade.god_rays(img, sun_xy=(0.75, 0.25), strength=0.4)
    assert rays.mean() > img.mean()


def test_chromatic_aberration_moves_color_channels(img):
    out = grade.chromatic_aberration(img, amount=2.0)
    assert not np.allclose(out[:, :, 0], img[:, :, 0])
    assert np.allclose(out[:, :, 1], img[:, :, 1])       # القناة الخضراء ما بتتحركش


def test_tonemap_no_clipping(img):
    hot = img * 4.0
    out = grade.film_tonemap(hot, exposure=1.0)
    assert out.max() <= 1.0 and out.min() >= 0.0
    assert out.mean() < hot.mean()


def test_clean_preset_is_identity(img):
    out = grade.apply(img, preset="clean")
    assert np.allclose(out, img, atol=1e-6)


def test_quality_report_fields(img):
    r = grade.quality_report((img * 255).astype(np.uint8))
    for k in ("mean_lum", "contrast", "saturation", "sharpness", "black_clip", "white_clip"):
        assert k in r
    assert r["black_clip"] >= 0 and r["white_clip"] >= 0


def test_uint8_input_supported(img):
    out = grade.apply((img * 255).astype(np.uint8), preset="cinema_warm")
    assert out.dtype == np.float32 and out.shape == img.shape
