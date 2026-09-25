"""اختبارات الإضافات البصرية والموسيقى — الإضافات أساسية في كل فيديو."""
import sys, pathlib, random
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import fx, music


def _frame(h=54, w=96):
    return (np.random.default_rng(0).random((h, w, 3)) * 255).astype(np.uint8)


def test_every_fx_kind_changes_or_keeps_shape():
    fr = _frame()
    for kind in fx.KINDS:
        out = fx.apply(fr, {"kind": kind, "strength": 0.8, "dur": 2.0, "seed": 3}, t=0.5)
        assert out.shape == fr.shape and out.dtype == np.uint8, kind
    # كل الأنواع لازم يكون ليها تنفيذ حقيقي
    assert len(fx._FUNCS) == len(fx.KINDS)


def test_fx_plan_is_capped_and_relevant():
    plan = fx.plan(random.Random(1), "satisfying", 5)
    assert len(plan) == 5
    for effs in plan:
        assert 1 <= len(effs) <= 2
        assert all(e["kind"] in fx.KINDS for e in effs)
        assert all(0.2 <= e["strength"] <= 1.0 for e in effs)


def test_fx_actually_changes_pixels():
    fr = np.zeros((40, 60, 3), np.uint8)
    out = fx.apply(fr, {"kind": "light_leak", "strength": 1.0, "dur": 2.0, "seed": 1}, t=0.5)
    assert int(out.sum()) > 0
    out2 = fx.apply_all(fr, [{"kind": "sparkle_dust", "strength": 1.0, "dur": 2.0, "seed": 2}], t=0.4)
    assert int(out2.sum()) > 0


def test_fx_respects_timing_windows():
    fr = _frame()
    eff = {"kind": "flare", "at": 2.0, "dur": 1.0, "strength": 1.0, "seed": 5}
    assert np.array_equal(fx.apply_all(fr, [eff], t=0.1), fr)      # قبل ميعاده
    assert not np.array_equal(fx.apply_all(fr, [eff], t=2.4), fr)  # جوه ميعاده


def test_music_styles_all_render_and_are_sane():
    for style in music.STYLES():
        x = music.bed(style, 3.0, seed=9)
        assert x.ndim == 2 and x.shape[1] == 2 and x.shape[0] > 44100
        assert np.isfinite(x).all()
        assert 0.02 < float(np.abs(x).max()) <= 0.93
    x = music.bed("music_box", 2.0)
    assert float(np.abs(x).max()) > 0.05      # فيها صوت فعلًا مش صمت


def test_music_loop_is_seamless_and_stable_level():
    a = music.bed("warm_pad", 4.0, seed=4)
    b = music.bed("warm_pad", 4.0, seed=4)
    assert np.allclose(a, b, atol=1e-6)                          # ثابتة بنفس البذرة
    c = music.bed("lofi_keys", 4.0, seed=5)
    ra = float(np.sqrt((a ** 2).mean())); rc = float(np.sqrt((c ** 2).mean()))
    assert abs(ra - rc) / max(ra, rc) < 0.6                      # نفس المستوى تقريبًا
    edge = np.abs(a[-64:] - a[:64]).mean()
    assert edge < 0.35                                           # مفيش قطع فاضح عند نقطة الحلقة


def test_music_bed_is_exactly_asked_length():
    """الطول بالظبط زي ما اتطلب — ده كان بيقصّر الفيديوهات 1.4 ث قبل كده."""
    for sec in (4.0, 9.5, 30.0):
        a = music.bed("warm_pad", sec, seed=5)
        assert abs(len(a) / music.SR - sec) < 0.01, f"{sec} ث طلعت {len(a)/music.SR:.2f} ث"
        assert a.shape[1] == 2


def test_outro_runs_full_length_with_audio(tmp_path):
    """شاشة النهاية لازم تكمّل طولها كامل بالنغمات — مش تتقطع عند آخر نغمة."""
    from engine import editor, proc
    p = editor.long_outro(tmp_path, 6.0, seed=9)
    assert p.exists()
    d = proc.duration(p)
    assert d is not None and abs(d - 6.0) < 0.15, f"الخاتمة طلعت {d} ث"
