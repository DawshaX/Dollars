"""اختبارات تحريك الشخصيات (2.5D Cutout)."""
import numpy as np
import pytest

from engine import cutout


STICKERS = sorted(p.stem for p in (cutout.STICKERS).glob("*.png"))


def test_all_stickers_load():
    assert len(STICKERS) >= 30
    for n in STICKERS:
        img = cutout.load_sprite(n)
        assert img.size[0] > 50 and img.mode == "RGBA"


def test_unknown_sticker_fails_loudly():
    with pytest.raises(KeyError):
        cutout.load_sprite("no_such_sticker")


@pytest.mark.parametrize("move", cutout.MOVES)
def test_every_move_returns_sane_pose(move):
    a = cutout.Actor("nono_happy", move=move)
    for t in (0.0, 1.3, 3.7, 7.9):
        p = a.pose(t)
        assert 0.0 <= p["alpha"] <= 1.0
        assert 0.05 < p["scale"] < 3.0
        assert abs(p["dx"]) < 1.0 and abs(p["dy"]) < 1.0


def test_hop_actually_lifts_and_lands():
    a = cutout.Actor("nono_happy", move="hop", loop=4.0)
    ys = [a.pose(t / 20 * 4)["dy"] for t in range(20)]
    assert min(ys) < -0.05           # بينط فوق
    assert max(ys) > -0.02           # وبيرجع لأرضه


def test_loop_move_is_periodic():
    a = cutout.Actor("koko_happy", move="idle", loop=6.0)
    p0, p1 = a.pose(0.3), a.pose(6.3)
    assert abs(p0["dy"] - p1["dy"]) < 1e-9 and abs(p0["scale"] - p1["scale"]) < 1e-9


def test_blink_happens_but_rarely():
    a = cutout.Actor("nono_happy", blink=True)
    hits = sum(1 for i in range(2000) if a.blink_state(i / 60))
    assert 0 < hits < 200            # بيرمش بس مش طول الوقت


def test_actor_without_blink_pair_never_blinks():
    a = cutout.Actor("star", blink=True)
    assert not any(a.blink_state(i / 30) for i in range(300))


def test_layer_composes_on_background():
    bg = np.full((120, 200, 3), 0.25, np.float32)
    lay = cutout.Layer(200, 120)
    lay.add(cutout.Actor("nono_happy", x=0.5, y=0.75, scale=0.55, move="idle"))
    out = lay.compose(bg, 1.0)
    assert out.shape == bg.shape
    assert float(np.abs(out - bg).mean()) > 0.01          # الشخصية بان عليها
    assert out.dtype == np.float32 and out.min() >= 0 and out.max() <= 1.0


def test_shadow_appears_under_actor():
    bg = np.full((160, 240, 3), 0.6, np.float32)
    lay = cutout.Layer(240, 160)
    a = cutout.Actor("nono_happy", x=0.5, y=0.7, scale=0.5)
    lay.add(a)
    out = lay.compose(bg, 0.0)
    y = int(0.7 * 160 + 0.5 * 160 * 0.06)
    band = out[max(0, y - 3):y + 4, 100:140].mean()
    assert band < bg[100:140].mean()                      # الظل غمّق الأرض


def test_enter_exit_fade():
    a = cutout.Actor("nono_happy", move="idle", enter=2.0, exit=4.0)
    assert a.pose(1.0)["alpha"] < 0.05
    assert a.pose(3.0)["alpha"] > 0.9
    assert a.pose(5.0)["alpha"] < 0.05


def test_unknown_move_fails_loudly():
    with pytest.raises(KeyError):
        cutout.Actor("nono_happy", move="moonwalk")
