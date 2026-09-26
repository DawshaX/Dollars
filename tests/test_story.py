"""اختبارات مُركّب الحِكايات بلا كلام."""
import numpy as np
import pytest

from engine import story, visuals, grade, meta


def test_bundled_stories_are_valid():
    stories = story.all_stories()
    assert len(stories) >= 2
    for s in stories:
        st = story.Story(s)
        assert st.validate() == [], f"{st.id}: {st.validate()}"
        assert 1.0 <= st.duration <= 240.0


def test_load_by_id_and_unknown():
    st = story.load("nono_rain")
    assert st.id == "nono_rain" and st.beats
    with pytest.raises(KeyError):
        story.load("not_a_story")


def test_validation_catches_text_on_screen():
    st = story.load("nono_rain")
    bad = dict(st.d, beats=[dict(st.beats[0], caption="مرحبا")])
    assert any("بلا كلام" in p for p in story.Story(bad).validate())


def test_validation_catches_bad_scene_and_sfx():
    st = story.load("nono_rain")
    bad = dict(st.d, beats=[dict(st.beats[0], scene="matrix", sfx=[{"name": "laser"}])])
    problems = story.Story(bad).validate()
    assert any("matrix" in p for p in problems) and any("laser" in p for p in problems)


def test_validation_catches_too_long_and_too_short():
    st = story.load("nono_rain")
    long_ = dict(st.d, beats=[dict(st.beats[0], dur=300.0)])
    assert any("أطول من" in p for p in story.Story(long_).validate())
    tiny = dict(st.d, beats=[dict(st.beats[0], dur=0.05)])
    assert story.Story(tiny).validate()


def test_audio_has_ambience_and_cues():
    st = story.load("nono_rain")
    x = story.build_audio(st.beats, st.ambient)
    assert x.size > st.duration * 44100 * 0.9
    assert float(np.abs(x).max()) <= 0.98
    assert float(np.abs(x).mean()) > 1e-4                 # فيه صوت فعلي


def test_audio_silent_when_nothing_asked():
    st = story.load("nono_rain")
    beats = [dict(b, sfx=[]) for b in st.beats]
    x = story.build_audio(beats, None)
    assert float(np.abs(x).max()) < 1e-6


def test_metadata_is_youtube_ready():
    st = story.load("nono_rain")
    md = st.metadata()
    assert meta.validate(md) == []
    assert md["pillar"] == "story"
    assert len(md["titles"]) == 3 and md["kind"] in ("short", "long")
    assert "wordless" in md["titles"][0].lower() or "story" in md["titles"][0].lower()


def test_render_produces_video_with_audio(tmp_path):
    data = {"id": "tiny", "title": "t", "ambient": None, "fps": 8, "size": [160, 90],
            "look": "clean", "beats": [
                {"scene": "harmonograph", "dur": 0.6, "look": "clean", "transition": "none",
                 "chars": [{"who": "nono_happy", "x": 0.5, "y": 0.7, "scale": 0.5, "move": "hop",
                            "cycles": 1.0}], "sfx": [{"at": 0.2, "name": "pop"}]},
                {"scene": "starfield", "dur": 0.6, "look": "clean", "transition": "fade",
                 "chars": [], "sfx": [{"at": 0.1, "name": "ding"}]}]}
    st = story.Story(data)
    assert st.validate() == []
    out = st.render(tmp_path / "tiny.mp4", verbose=False)
    assert out.exists() and out.stat().st_size > 3000
    probe = __import__("subprocess").run([visuals.FFMPEG, "-hide_banner", "-i", str(out)],
                                        capture_output=True).stderr.decode("utf-8", "ignore")
    assert "Audio: aac" in probe
    # الملصقات جزء من المونتاج في القصة كمان (ملفات حقيقية بس)
    from engine import editor as _ed
    assert st._last_stickers >= 1, "القصة اترسمت بلا ملصقات"
    assert st._last_sticker_names and set(st._last_sticker_names) <= set(_ed._sticker_files())


def test_transitions_render_without_error():
    bg = np.full((90, 160, 3), 0.3, np.float32)
    for kind in story.TRANSITIONS:
        out = story._blend_transition(bg, kind, 0.5, 1.0, 160, 90, 12)
        assert out.shape == bg.shape and np.isfinite(out).all()
        assert out.min() >= 0 and out.max() <= 1.0


def test_inventory_reports_status():
    text = story.inventory()
    assert "nono_rain" in text and "✅" in text
