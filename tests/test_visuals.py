"""اختبارات محرّك المشاهد: الحركة حقيقية · الحلقة مثالية · الترميز سليم."""
import pathlib
import subprocess

import numpy as np
import pytest

from engine import visuals as V

SMALL = dict(w=320, h=180, fps=12)


def _dur(path) -> float:
    out = subprocess.run([V.FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True)
    for line in out.stderr.decode("utf-8", "ignore").splitlines():
        if "Duration:" in line:
            hh, mm, ss = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(hh) * 3600 + int(mm) * 60 + float(ss)
    raise AssertionError("مفيش مدة")


@pytest.mark.parametrize("name", sorted(V.SCENES))
def test_scene_renders(name):
    sc = V.make_scene(name, **SMALL)
    f = sc.frame(0.0)
    assert f.shape == (180, 320, 3) and f.dtype == np.uint8


@pytest.mark.parametrize("name", sorted(n for n, c in V.SCENES.items() if not c.stateful))
def test_loop_is_seamless(name):
    """الحلقة لازم تكون مستمرة رياضيًا: الكادر الأول = الكادر الأخير."""
    sc = V.make_scene(name, **SMALL)
    a, b = sc.raw(0.0), sc.raw(sc.loop_seconds)
    assert np.abs(a - b).max() < 0.02, f"{name}: فرق {np.abs(a - b).max()}"


@pytest.mark.parametrize("name", sorted(V.SCENES))
def test_scene_is_alive_not_a_still(name):
    """ممنوع «صور وخلاص»: لازم يكون فيه حركة حقيقية بين أي لحظتين."""
    sc = V.make_scene(name, **SMALL)
    d = float(np.abs(sc.raw(0.0) - sc.raw(sc.loop_seconds * 0.37)).mean())
    assert d > 0.002, f"{name}: حركة ضعيفة جدًا ({d})"


def test_sand_table_loops_over_two_cycles():
    sc = V.make_scene("sand_table", w=240, h=135, fps=10)
    sc.reset()
    fps = 10
    F = int(round(sc.loop_seconds * fps))
    first = sc.raw(0.0).copy()
    for i in range(1, 2 * F):
        fr = sc.raw(i / fps)
        if i == F:
            d = float(np.abs(fr - first).mean())
            assert d < 0.06, f"طاولة الرمل مش حلقة: فرق {d}"


def test_black_screen_exists_and_breathes():
    sc = V.black_screen(**{**SMALL, "fps": 12})
    a, b = sc.raw(0.0), sc.raw(sc.loop_seconds / 2)
    assert a.max() < 20 and float(np.abs(a - b).mean()) < 0.02      # أسود فعليًا وبلا حركة مزعجة


def test_encode_and_long_video(tmp_path):
    sc = V.make_scene("harmonograph", w=240, h=135, fps=12)
    loop = V.encode(sc, 2.0, tmp_path / "loop.mp4", out_w=480, out_h=270, crf=28)
    assert loop.stat().st_size > 2000
    assert abs(_dur(loop) - 2.0) < 0.3
    long = V.long_video(loop, tmp_path / "long.mp4", 6.0)
    assert abs(_dur(long) - 6.0) < 0.4
    assert long.stat().st_size > loop.stat().st_size


def test_long_video_with_looped_audio(tmp_path):
    from engine import ambient
    sc = V.make_scene("starfield", w=240, h=135, fps=12)
    loop = V.encode(sc, 2.0, tmp_path / "loop.mp4", out_w=480, out_h=270, crf=30)
    wav = ambient.make("rain_only", 2.0, tmp_path / "rain.wav")
    assert wav.exists()
    out = V.long_video(loop, tmp_path / "with_audio.mp4", 5.0, audio_wav=wav)
    assert abs(_dur(out) - 5.0) < 0.4
    probe = subprocess.run([V.FFMPEG, "-hide_banner", "-i", str(out)], capture_output=True)
    assert "Audio:" in probe.stderr.decode("utf-8", "ignore")


def test_unknown_scene_fails_loudly():
    with pytest.raises(KeyError):
        V.make_scene("nonexistent_movie")


def test_performance_is_reasonable():
    """سرعة مقبولة: كادر عند 320×180 في أقل من ثانية (المصنع بيرندر حلقة مرة ويتكرّرها)."""
    import time
    sc = V.make_scene("rain_glass", **SMALL)
    sc.frame(0.0)
    t0 = time.time()
    for i in range(4):
        sc.frame(i * 0.3)
    assert (time.time() - t0) / 4 < 1.0
