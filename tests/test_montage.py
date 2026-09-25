"""اختبارات المونتاج الإجباري: كل نوع لازم يطلع مركّب (مقاطع + إضافات + صوت + موسيقى)."""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import editor, music, proc, refs, story


def test_recipe_drives_look_moves_and_scenes():
    r = refs.recipe_for("satisfying")
    assert r["look"] in ("satisfying", "cinema_cool", "cinema_night", "cinema_warm", "clean", "story")
    assert r["music"] in music.STYLES()
    shots = editor.plan_shots("satisfying", 15, seed=5, moves=r["moves"], scenes=r["scenes"])
    assert {s["move"] for s in shots} <= set(r["moves"])
    assert {s["scene"] for s in shots} <= set(r["scenes"])
    assert shots[0]["cues"], "أول مقطع لازم فيه مؤثر خطف"
    assert all(s.get("fx") for s in shots), "كل مقطع لازم فيه إضافة بصرية"


def test_plan_shots_never_repeats_scene_back_to_back():
    shots = editor.plan_shots("satisfying", 30, seed=2, scenes=["sand_table", "pendulum_wave", "harmonograph"])
    assert all(a["scene"] != b["scene"] for a, b in zip(shots, shots[1:]))


def test_stories_always_have_music_and_fx():
    for s in story.all_stories():
        st = story.Story(s)
        assert st.music in music.STYLES(), f"{st.id}: مفيش موسيقى"
        fx = st.fx_summary()
        assert len(fx) == len(st.beats) and all(layer for layer in fx), f"{st.id}: بيت بلا إضافة"


def test_short_is_assembled_with_montage_layers(tmp_path):
    r = refs.recipe_for("kinetic")
    rec = editor.Editor(str(tmp_path), seed=4).make(
        "satisfying_short", seconds=6, look=r["look"], moves=r["moves"], scenes=r["scenes"], music=r["music"])
    v = pathlib.Path(rec["video"])
    assert v.exists() and v.stat().st_size > 50_000
    md = rec["meta"]["montage"]
    assert md["shots"] >= 1 and md["fx_layers"] >= 1 and md["sfx_cues"] >= 1
    assert md["music"] == r["music"] and md["look"] == r["look"]
    assert md["camera_moves"]                      # كاميرا بتتحرك
    assert rec["meta"]["shot_list"][0]["fx"]       # الإضافات مسجّلة لكل مقطع
    out = subprocess.run([proc.FFMPEG, "-hide_banner", "-i", str(v)], capture_output=True).stderr.decode()
    assert "Audio: aac" in out                     # الفيديو بصوت من أول لآخر لحظة


def test_long_format_caps_size_for_long_videos():
    """10 ساعات ما تبقاش جيجابايتات: المقاس والبتريت بيتظبطوا حسب الطول."""
    small = editor.long_format(3)
    big = editor.long_format(10)
    assert small["w"] == 1920 and small["maxrate"] == "1200k"
    assert big["w"] == 1280 and big["h"] == 720
    est_mb = float(big["maxrate"][:-1]) * 10 * 3600 / 8 / 1000
    assert est_mb <= big["cap_mb"] * 1.05, f"الحجم المتوقع {est_mb:.0f} ميجا أكبر من السقف"


def test_montage_assembles_at_720p_without_reencode(tmp_path):
    """مسارات المونتاج لازم تتلزق بنفس المقاس والبتريت (بلا إعادة ترميز) وبمدة صح."""
    from engine import ambient, proc, visuals
    sc = visuals.make_scene("starfield", w=480, h=270, fps=30)
    loop = tmp_path / "loop.mp4"
    visuals.encode(sc, 2.0, loop, out_w=1280, out_h=720, crf=23, maxrate="700k", cinema="cinema_night")
    body = tmp_path / "body.mp4"
    visuals.long_video(loop, body, 4.0)
    intro = editor.long_intro(tmp_path, 3.0, seed=3, out_w=1280, out_h=720)
    outro = editor.long_outro(tmp_path, 3.0, seed=9, out_w=1280, out_h=720)
    joined = editor._concat([intro, body, outro], tmp_path / "joined.mp4")
    d = proc.duration(joined)
    assert d is not None and abs(d - 10.0) < 1.0, f"الملزوق طلع {d} ث"
    info = subprocess.run([proc.FFMPEG, "-hide_banner", "-i", str(joined)], capture_output=True).stderr.decode()
    assert "1280x720" in info, "المقاس اتغيّر في اللزق"
