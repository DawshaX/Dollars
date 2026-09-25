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
