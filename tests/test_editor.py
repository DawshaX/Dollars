"""اختبارات محرّك المونتاج: خطة مقاطع · كاميرا · صوت ممزوج · غلاف · فيديو كامل."""
import pathlib
import subprocess

import numpy as np
import pytest

from engine import editor, proc, sfx, visuals


def test_plan_shots_covers_duration_and_has_hooks():
    shots = editor.plan_shots("satisfying", 25.0, seed=4)
    total = sum(s["dur"] for s in shots)
    assert 24.0 <= total <= 30.0
    assert all(s["scene"] in visuals.SCENES for s in shots)
    assert all(s["move"] in editor.MOVES for s in shots)
    assert any(c["name"] in sfx.SFX for s in shots for c in s["cues"])   # أول مقطع فيه مؤثر
    assert shots[0]["cues"], "أول مقطع لازم يخطف العين بمؤثر"
    assert all(s["dur"] <= 9.0 for s in shots)


def test_plan_shots_is_deterministic_per_seed():
    a = editor.plan_shots("satisfying", 20.0, seed=11)
    b = editor.plan_shots("satisfying", 20.0, seed=11)
    c = editor.plan_shots("satisfying", 20.0, seed=12)
    assert [s["scene"] for s in a] == [s["scene"] for s in b]
    assert [s["scene"] for s in a] != [s["scene"] for s in c]


def test_ambience_shots_use_sleep_scenes():
    shots = editor.plan_shots("ambience", 18.0, seed=2)
    assert all(s["scene"] in visuals.SLEEP_SCENES for s in shots)


def test_camera_moves_change_the_frame():
    frame = (np.random.default_rng(1).random((90, 160, 3)) * 255).astype(np.uint8)
    for move in editor.MOVES:
        out = editor.camera(frame, move, 0.8)
        assert out.shape == frame.shape
        if move != "still":
            assert not np.array_equal(out, frame), f"{move} مش بيعمل أي حركة"


def test_mix_audio_timing_and_levels():
    shots = editor.plan_shots("satisfying", 10.0, seed=5)
    x = editor.mix_audio(10.0, shots, ambient_name="rain_only")
    assert x.shape == (10 * 44100, 2)
    assert np.abs(x).max() <= 1.0 and np.abs(x).max() > 0.2   # مستوى معقول
    assert np.abs(x).mean() > 1e-4                            # مش صامت


def test_thumbnail_is_written_with_text(tmp_path):
    p = editor.thumbnail("valley_lake", ["10 HOURS", "RAIN ON WINDOW"],
                         tmp_path / "t.jpg", sticker="star")
    assert p.exists() and p.stat().st_size > 5000
    from PIL import Image
    im = Image.open(p)
    assert im.size == (1280, 720)


@pytest.mark.parametrize("kind,seconds", [("satisfying_short", 6.0), ("ambience_short", 6.0)])
def test_full_short_renders_with_audio_thumbnail_and_metadata(tmp_path, kind, seconds):
    ed = editor.Editor(str(tmp_path), seed=9)
    rec = ed.make(kind, seconds=seconds)
    video = pathlib.Path(rec["video"])
    assert video.exists() and video.stat().st_size > 20000
    out = subprocess.run([proc.FFMPEG, "-hide_banner", "-i", str(video)], capture_output=True).stderr.decode()
    assert "Video: h264" in out and "Audio: aac" in out
    assert pathlib.Path(rec["thumbnail"]).exists()
    md = rec["meta"]
    assert md["titles"] and md["description"] and md["shot_list"]


def test_long_video_is_built_without_reencode(tmp_path):
    ed = editor.Editor(str(tmp_path), seed=3)
    rec = ed.make("sleep_long", hours=0.0028, scene="starfield", audio="calm_night", loop_seconds=4.0)
    v = pathlib.Path(rec["video"])
    assert v.exists()
    out = subprocess.run([proc.FFMPEG, "-hide_banner", "-i", str(v)], capture_output=True).stderr.decode()
    # المونتاج إجباري: 10 ث متن + مقدمة 12 ث + خاتمة 10 ث ≈ 32 ث (بلا إعادة ترميز للمتن)
    import re
    d = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    secs = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    assert 30 <= secs <= 36, f"مدة الطويلة غلط: {secs}"
    assert rec["meta"]["chapters"]           # الطويلة لازم يكون ليها فصول
    assert rec["meta"]["chapters"][0].startswith("0:00")  # أول فصل عند المقدمة
    m = rec["meta"]["montage"]                            # المونتاج مسجّل بالكامل
    assert m["assembled"] and m["intro_seconds"] == 12.0 and m["outro_seconds"] == 10.0
    assert m["body_reencoded"] is False and m["music"] == "warm_pad"
