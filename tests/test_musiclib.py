"""اختبارات محرّك الموسيقى الحقيقية (engine/musiclib.py) + الطبقة الجرافيكية (overlays).

المهم هنا: **أمان الحقوق** (مفيش NC/ND · الكريديت بيتكتب) + إن الملفات الصامتة تترفض.
"""
import numpy as np
import pytest
from PIL import Image

from engine import musiclib, overlays


# ───────────────────────── الحقوق (أهم حاجة) ─────────────────────────

@pytest.mark.parametrize("lic,url", [
    ("cc0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    ("CC0 1.0", ""),
    ("BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    ("publicdomain", ""),
    ("by-sa", "https://creativecommons.org/licenses/by-sa/4.0/"),
])
def test_license_ok_accepts_profit_safe(lic, url):
    assert musiclib._license_ok(lic, url) is True


@pytest.mark.parametrize("lic,url", [
    ("by-nc", "https://creativecommons.org/licenses/by-nc/4.0/"),
    ("by-nd", "https://creativecommons.org/licenses/by-nd/4.0/"),
    ("nc", ""),
    ("nd", ""),
    ("", ""),                      # مجهولة ⇒ ممنوعة (مخاطرة حقوق)
])
def test_license_ok_rejects_noncommercial_or_unknown(lic, url):
    assert musiclib._license_ok(lic, url) is False


def test_cc0_needs_no_credit_but_ccby_does():
    assert musiclib._needs_credit("CC0 1.0") is False
    assert musiclib._needs_credit("BY 4.0") is True


def test_credits_line_has_title_author_and_license():
    lines = musiclib.credits([{"title": "Calm Waves", "creator": "Someone",
                               "license": "BY 4.0",
                               "license_url": "https://creativecommons.org/licenses/by/4.0/",
                               "page": "https://freesound.org/x", "needs_credit": True}])
    assert lines and "Calm Waves" in lines[0] and "Someone" in lines[0] and "BY 4.0" in lines[0]
    assert "creativecommons.org" in lines[0]


def test_credits_skips_cc0():
    assert musiclib.credits([{"title": "x", "creator": "y", "license": "CC0",
                              "needs_credit": False}]) == []


# ───────────────────────── الترتيب والكاش ─────────────────────────

def test_relevance_prefers_matching_mood_and_longer():
    good = {"title": "cinematic documentary ambient music", "tags": ["ambient"],
            "seconds": 180, "needs_credit": False, "creator": "x"}
    bad = {"title": "dog barking", "tags": [], "seconds": 12, "needs_credit": True, "creator": ""}
    assert musiclib._relevance(good, "facts") > musiclib._relevance(bad, "facts")


def test_cache_lives_outside_workspace():
    assert "dollars_music" in str(musiclib.CACHE)


def test_trim_cache_keeps_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(musiclib, "CACHE", tmp_path)
    import os
    for i in range(6):
        f = tmp_path / f"t{i}.mp3"
        f.write_bytes(b"0" * 2_000_000)
        os.utime(f, (1_700_000_000 + i, 1_700_000_000 + i))
    freed = musiclib.trim_cache(max_mb=5, keep_min=2)
    left = sorted(p.name for p in tmp_path.glob("*.mp3"))
    assert freed >= 3 and left[-1] == "t5.mp3"


# ───────────────────────── الرندر الصوتي ─────────────────────────

def _tone(path, seconds=3.0, freq=220.0, rate=44100):
    import subprocess
    from engine import proc
    subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate={rate}",
                    "-ac", "2", str(path)], check=True)
    return path


@pytest.mark.slow
def test_probe_and_decode_real_audio(tmp_path):
    f = _tone(tmp_path / "tone.wav", 4.0)
    d = musiclib.probe_audio(f)
    assert d and 3.5 < d["seconds"] < 4.6 and d["rms"] > 0.03, f"قياس الصوت غلط: {d}"
    x = musiclib.decode(f, 2.0)
    assert x is not None and x.shape[0] == 2 * musiclib.SR and x.shape[1] == 2


@pytest.mark.slow
def test_decode_loops_short_audio(tmp_path):
    f = _tone(tmp_path / "short.wav", 1.0)
    x = musiclib.decode(f, 3.0)          # أطول من الملف ⇒ يلفّه
    assert x is not None and x.shape[0] == 3 * musiclib.SR


def test_silent_file_is_rejected(tmp_path, monkeypatch):
    from engine import proc
    import subprocess
    monkeypatch.setattr(musiclib, "CACHE", tmp_path)
    f = tmp_path / "src.wav"
    subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=stereo", "-t", "20", str(f)], check=True)
    # رابط وهمي: بنستخدم ملف محلي عبر file://
    item = {"url": f.as_uri(), "title": "silent"}
    assert musiclib.download(item) is None
    assert item.get("rejected") in ("silent_or_short", "size", None) or item.get("error")


# ───────────────────────── الطبقة الجرافيكية ─────────────────────────

def _frame(h=240, w=135):
    fr = np.zeros((h, w, 3), np.uint8)
    fr[:, :, 2] = 80
    fr[::3] = 120
    return fr


def test_progress_bar_changes_pixels():
    fr = _frame()
    out0 = overlays.progress_bar(fr, 0.0)
    out1 = overlays.progress_bar(fr, 0.9)
    assert out0.shape == fr.shape
    assert float(np.abs(out1.astype(int) - out0.astype(int)).mean()) > 0.5, "الشريط لازم يتقدّم"


def test_hook_badge_only_in_first_seconds():
    fr = _frame()
    early = overlays.hook_badge(fr, "Watch this", 0.6, dur=3.0)
    late = overlays.hook_badge(fr, "Watch this", 5.0, dur=3.0)
    assert float(np.abs(early.astype(int) - fr.astype(int)).mean()) > 0.3
    assert np.array_equal(late, fr), "بعد المدة مفيش بادج"


def test_caption_card_draws_and_respects_window():
    fr = _frame(320, 180)
    inside = overlays.caption_card(fr, "The ocean glows in the dark", 1.5, 1.0, 3.0)
    outside = overlays.caption_card(fr, "The ocean glows in the dark", 9.0, 1.0, 3.0)
    assert float(np.abs(inside.astype(int) - fr.astype(int)).mean()) > 1.0
    assert np.array_equal(outside, fr)


def test_watermark_visible_and_optional():
    fr = _frame(360, 200)
    out = overlays.watermark(fr, "@xDaw_NoVa")
    assert float(np.abs(out.astype(int) - fr.astype(int)).mean()) > 0.05
    assert np.array_equal(overlays.watermark(fr, ""), fr)


def test_sticker_draw_without_network(monkeypatch):
    im = Image.new("RGBA", (72, 72), (255, 0, 0, 255))
    monkeypatch.setattr(overlays, "sticker", lambda code: im)
    fr = _frame()
    out = overlays.draw_sticker(fr, "fire", 2.0, 1.5, 2.0)
    assert float(np.abs(out.astype(int) - fr.astype(int)).mean()) > 0.5
    same = overlays.draw_sticker(fr, "fire", 9.0, 1.5, 2.0)
    assert np.array_equal(same, fr), "بره النافذة مفيش ملصق"


def test_sticker_missing_is_silent(monkeypatch):
    monkeypatch.setattr(overlays, "sticker", lambda code: None)
    fr = _frame()
    assert np.array_equal(overlays.draw_sticker(fr, "nope", 1.0, 0.5, 2.0), fr)


def test_plan_stickers_inside_duration_and_spaced():
    plan = overlays.plan_stickers("facts", 30, seed=3, count=3)
    assert plan, "لازم يخطّط ملصقات"
    for s in plan:
        assert 0 < s["at"] < 29 and s["dur"] > 1.0
        assert 0.05 < s["x"] < 0.95 and 0.05 < s["y"] < 0.95
    ats = [s["at"] for s in plan]
    assert ats == sorted(ats) and all(b - a >= 2.0 for a, b in zip(ats, ats[1:])), "متباعدة"


def test_plan_stickers_short_video_gets_fewer():
    assert len(overlays.plan_stickers("asmr", 12, seed=1, count=3)) <= 1


def test_emoji_credit_present():
    assert "Twemoji" in overlays.EMOJI_CREDIT and "CC-BY" in overlays.EMOJI_CREDIT
