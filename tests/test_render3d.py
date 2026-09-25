"""اختبارات محرّك 3D: منظور حقيقي · حلقة مثالية · عمق · ضباب · أجسام."""
import numpy as np
import pytest

from engine import render3d, visuals, grade

SMALL = dict(w=200, h=120, fps=10)


@pytest.mark.parametrize("name", sorted(render3d.SCENES_3D))
def test_scene_renders_with_depth(name):
    sc = render3d.make_3d(name, **SMALL)
    img = sc.raw(0.0)
    d = sc.depth(0.0)
    assert img.shape == (120, 200, 3) and d.shape == (120, 200)
    assert np.isfinite(img).all() and np.isfinite(d).all()
    assert img.mean() > 0.005                       # مش شاشة سوداء فاضية
    assert 0.0 <= d.min() and d.max() <= 1.0


@pytest.mark.parametrize("name", ["valley_lake", "dunes_moon", "planet_rings"])
def test_loop_is_seamless_3d(name):
    sc = render3d.make_3d(name, **SMALL)
    a, b = sc.raw(0.0), sc.raw(sc.loop_seconds)
    assert np.abs(a - b).max() < 0.06, f"{name}: فرق الحلقة {np.abs(a-b).max()}"


@pytest.mark.parametrize("name", sorted(render3d.SCENES_3D))
def test_really_moves_camera_and_world(name):
    """كاميرا بتتحرك ومشهد حيّ — مش صورة ثابتة."""
    sc = render3d.make_3d(name, **SMALL)
    a, b = sc.raw(0.0), sc.raw(sc.loop_seconds * 0.4)
    assert float(np.abs(a - b).mean()) > 0.004, f"{name}: حركة ضعيفة"


def test_terrain_has_real_parallax_and_fog():
    """منظور حقيقي: قريب أكبر من بعيد + الضباب يخفّف البعيد."""
    sc = render3d.make_3d("valley_lake", **SMALL)
    img = sc.raw(0.0); d = sc.depth(0.0)
    assert d.min() < d.max()                          # فيه نطاق مسافات
    far = img[d > 0.8].mean() if (d > 0.8).any() else 0
    near = img[d < 0.4].mean() if (d < 0.4).any() else 1
    assert far >= near * 0.9                          # البعيد مش أغمق فجأة (ضباب صح)


def test_objects_are_placed_on_terrain():
    sc = render3d.make_3d("snow_pines", **SMALL)
    assert len(sc.objects) > 20
    for ox, oz, size, kind, col in sc.objects[:10]:
        assert kind in ("pine", "rock") and size > 0
        assert -sc.world_size <= ox <= sc.world_size


def test_registered_in_engine_catalog():
    for name in render3d.SCENES_3D:
        assert name in visuals.SCENES
        sc = visuals.make_scene(name, **SMALL)
        assert sc is not None


def test_grade_works_on_3d_depth():
    sc = render3d.make_3d("dunes_moon", **SMALL)
    img = sc.raw(0.0); d = sc.depth(0.0)
    out = grade.apply(img, preset="cinema_warm", depth=d)
    assert out.shape == img.shape and 0 <= out.min() and out.max() <= 1


@pytest.mark.parametrize("size", [(200, 120), (480, 270), (641, 361)])
def test_no_index_errors_at_any_resolution(size):
    """🐞 الأخطاء العددية كانت بتكسر الراسم عند دقات معيّنة — لازم تشتغل على أي مقاس."""
    w, h = size
    sc = render3d.make_3d("valley_lake", w=w, h=h, fps=8)
    for i in range(3):
        img = sc.raw(i * 0.7)
        assert np.isfinite(img).all()


def test_unknown_3d_scene_fails_loudly():
    with pytest.raises(KeyError):
        render3d.make_3d("nope_scene")
