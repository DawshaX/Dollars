"""اختبارات محرّك الفيديو الحقيقي (engine/clips.py).

بنختبر: الروابط الخفيفة · حجب المصادر الوحشة (شرح/بيانات/نص مدمج) · الترتيب حسب الصلة ·
التقليم للكاش · رندر حقيقي قصير (smoke) بلوب ناعم.
"""
import pathlib
import subprocess

import numpy as np
import pytest

from engine import clips, proc


# ─────────────────────────── روابط خفيفة ───────────────────────────

def test_light_urls_for_wikimedia():
    url = "https://upload.wikimedia.org/wikipedia/commons/9/96/Night_to_Day.webm"
    light = clips._light_urls(url)
    assert light, "لازم نقترح نسخة أخف للديكود"
    assert "/transcoded/" in light[0] and "720p" in light[0]
    assert light[0].endswith("Night_to_Day.720p.vp9.webm")


def test_light_urls_empty_for_other_sources():
    assert clips._light_urls("https://cdn.pixabay.com/video/x.mp4") == []
    assert clips._light_urls("") == []


# ─────────────────────── حجب المصادر الوحشة ───────────────────────

@pytest.mark.parametrize("bad", [
    "NOAA CIRA data visualization of the storm",
    "Meteosat infrared animation",
    "Press conference: mission briefing",
    "How to edit videos — tutorial part 1",
    "Company promo trailer 2024",
    "Daily news update on the weather",
])
def test_title_blocked(bad):
    assert clips.title_ok(bad) is False


@pytest.mark.parametrize("good", [
    "Ocean surface waves 06",
    "Rain drops on a window at night",
    "Forest morning mist in the valley",
    "Earth from orbit — no text",
])
def test_title_allowed(good):
    assert clips.title_ok(good) is True


def test_is_clean_rejects_burn_in_text():
    q = {"frames": 6, "texty": 0.30, "flatblk": 0.0, "flat": 0.3, "sat": 40}
    assert clips.is_clean(q) is False, "نص مكتوب جوّه الفيديو = مرفوض"


def test_is_clean_rejects_synthetic_graphics():
    q = {"frames": 6, "texty": 0.0, "flatblk": 0.62, "flat": 0.5, "sat": 50}
    assert clips.is_clean(q) is False, "بلوكات مسطّحة = جرافيك/بيانات مش كاميرا"


def test_is_clean_rejects_unverifiable():
    assert clips.is_clean({"frames": 1}) is False, "لو ما قدرناش نعاين، مانخاطرش"
    assert clips.is_clean(None) is False


def test_is_clean_accepts_real_footage():
    # بحر حقيقي: مسطّح نسبيًا وتشبّع عالي — لكن مش جرافيك ولا نص
    q = {"frames": 6, "texty": 0.05, "flatblk": 0.004, "flat": 0.745, "sat": 128}
    assert clips.is_clean(q) is True


# ─────────────────────────── جمع المقاطع ───────────────────────────

def test_collect_filters_junk_and_dedupes(monkeypatch):
    fake = [
        {"source": "pexels", "id": "1", "url": "https://x/1.mp4", "title": "NOAA data visualization"},
        {"source": "pexels", "id": "2", "url": "https://x/2.mp4", "title": "Rain on window"},
        {"source": "pexels", "id": "3", "url": "https://x/2.mp4", "title": "rain on window close"},
        {"source": "pixabay", "id": "4", "url": "https://x/4.mp4", "title": "Window rain drops"},
        {"source": "pixabay", "id": "5", "url": "https://x/5.mp4", "title": "Interview with a farmer"},
    ]
    monkeypatch.setattr(providers_mod(), "pexels_videos", lambda q, per=5: [f for f in fake
                                                                           if f["source"] == "pexels"])
    monkeypatch.setattr(providers_mod(), "pixabay_videos", lambda q, per=5: [f for f in fake
                                                                            if f["source"] == "pixabay"])
    monkeypatch.setattr(providers_mod(), "nasa_videos", lambda q, per=3: [])
    monkeypatch.setattr(providers_mod(), "archive_videos", lambda q, per=3: [])
    monkeypatch.setattr(clips, "_wikimedia_videos", lambda q, per=3: [])
    monkeypatch.setattr(clips, "_nasa_videos", lambda q, per=3: [])

    out = clips.collect("rain on window", genre="sleep_ambience", n=6)
    urls = [i["url"] for i in out]
    assert "https://x/1.mp4" not in urls, "الجرافيك/البيانات لازم يترفض"
    assert "https://x/5.mp4" not in urls, "الإنترفيو مش footage"
    assert len(urls) == len(set(urls)), "ممنوع تكرار"


def test_collect_ranks_by_relevance(monkeypatch):
    monkeypatch.setattr(providers_mod(), "pexels_videos", lambda q, per=5: [
        {"source": "pexels", "id": "a", "url": "https://x/a.mp4", "title": "abstract texture"},
        {"source": "pexels", "id": "b", "url": "https://x/b.mp4", "title": "ocean waves at night"},
    ])
    monkeypatch.setattr(providers_mod(), "pixabay_videos", lambda q, per=5: [])
    monkeypatch.setattr(providers_mod(), "nasa_videos", lambda q, per=3: [])
    monkeypatch.setattr(providers_mod(), "archive_videos", lambda q, per=3: [])
    monkeypatch.setattr(clips, "_wikimedia_videos", lambda q, per=3: [])
    monkeypatch.setattr(clips, "_nasa_videos", lambda q, per=3: [])
    out = clips.collect("ocean waves night", genre="sleep_ambience", n=5)
    assert out and out[0]["id"] == "b", "المطابق للموضوع يبقى الأول"


def providers_mod():
    from engine import providers
    return providers


# ─────────────────────────── الكاش ───────────────────────────

def test_cache_is_outside_workspace():
    assert "dollars_clips" in str(clips.CACHE), "الكاش لازم يكون خارج الورك سبيس (سقف صارم)"
    assert pathlib.Path.cwd() not in clips.CACHE.parents or "dollars_clips" in str(clips.CACHE)


def test_trim_cache_removes_oldest(tmp_path, monkeypatch):
    monkeypatch.setattr(clips, "CACHE", tmp_path)
    for i in range(8):
        f = tmp_path / f"c{i}.mp4"
        f.write_bytes(b"0" * (3_000_000))
        import os
        os.utime(f, (1_700_000_000 + i, 1_700_000_000 + i))
    freed = clips.trim_cache(max_mb=12, keep_min=2)
    left = sorted(tmp_path.glob("*.mp4"))
    total = sum(f.stat().st_size for f in left) / 1e6
    assert freed >= 3 and total <= 12.0, f"لازم ينزل تحت السقف (فضل {total:.1f} ميجا)"
    assert left[-1].name == "c7.mp4", "الأحدث يفضل"


def test_credits_include_source_and_license():
    lines = clips.credits([{"source": "wikimedia", "page": "https://commons.wikimedia.org/x",
                            "license": "CC0"}])
    assert lines and "wikimedia" in lines[0] and "CC0" in lines[0]


# ─────────────────────────── رندر حقيقي (smoke) ───────────────────────────

def _make_clip(path: pathlib.Path, seconds: float = 2.0, seed: int = 0):
    """مقطع اختبار متحرك (مش ساكن) — من غير شبكة."""
    vf = (f"nullsrc=s=360x640:r=30:d={seconds},geq=r='128+80*sin(2*PI*(X+T*90)/90)':"
          f"g='60+50*cos(2*PI*(Y+T*70)/120)':b='90+70*sin(2*PI*(X+Y+T*120)/150)'")
    subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", vf, "-t", f"{seconds}", "-pix_fmt", "yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", str(path)], check=True)
    return path


@pytest.mark.slow
def test_render_reel_smoke(tmp_path):
    a = _make_clip(tmp_path / "a.mp4", 2.0)
    b = _make_clip(tmp_path / "b.mp4", 2.0)
    # ١٢ ثانية @ ١٢ كادر/ث = ١٤٤ كادر (لازم > 10*فps عشان اللوب يشتغل)
    out = clips.render_reel([a, b], tmp_path / "reel.mp4", seconds=12.0, w=180, h=320, fps=12,
                            seed=5, loop_back=True,
                            texts=[{"at": 0.2, "dur": 1.0, "text": "اختبار", "pos": "lower"}])
    assert out.exists() and out.stat().st_size > 20_000

    # كادرات فعلية: فيه حركة + اللوب رجع لأول كادر
    r = subprocess.run([proc.FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(out),
                        "-vf", "scale=90:160", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                       capture_output=True)
    arr = np.frombuffer(r.stdout, np.uint8)
    n = arr.size // (90 * 160)
    assert n >= 100, "لازم يطلع كادرات فعلية"
    fr = arr[:n * 90 * 160].reshape(n, 160, 90).astype(np.float32)
    motion = float(np.abs(np.diff(fr, axis=0)).mean())
    loop = float(np.abs(fr[0] - fr[-1]).mean())
    assert motion > 0.1, f"مفيش حركة كفاية ({motion:.3f})"
    assert loop < 12.0, f"اللوب مش ناعم ({loop:.2f})"


# ─────────────────── توحيد ملفات الحالة (منع فشل التشغيلات) ───────────────────

def test_state_union_merges_lists_and_dicts():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ms", "tools/merge_state.py")
    ms = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ms)
    ours = {"log": ["a", "b"], "meta": {"x": 1}, "keep": True}
    theirs = {"log": ["b", "c"], "meta": {"x": 9, "y": 2}, "keep": False}
    out = ms.union(ours, theirs)
    assert out["log"] == ["a", "b", "c"], "القوائم بتتّحد بلا تكرار"
    assert out["meta"]["y"] == 2 and out["meta"]["x"] == 1, "نسختنا ليها الأولوية"
    assert out["keep"] is True


def test_state_union_handles_deep_and_empty():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ms", "tools/merge_state.py")
    ms = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ms)
    assert ms.union({}, {"a": [1]}) == {"a": [1]}
    assert ms.union({"a": 1}, {}) == {"a": 1}
    nested = ms.union({"a": {"b": {"c": [1]}}}, {"a": {"b": {"c": [2], "d": 3}}})
    assert nested["a"]["b"]["c"] == [1, 2] and nested["a"]["b"]["d"] == 3


def test_nsfw_titles_are_blocked():
    """🚫 أي محتوى NSFW يترفض من العنوان (حماية للنشر/الربح)."""
    from engine import clips
    for bad in ["Close up ejaculation one quarter speed", "Naked woman walking",
                "Porn compilation", "Masturbation tutorial", "Sexy bikini girl",
                "Topless dance", "update onejaculation"]:
        assert not clips.title_ok(bad), bad
    for ok in ["Close-up of yellow flowers", "Sperm whale swimming and diving",
               "Bubble wrap crunching close up", "Rain on window at night"]:
        assert clips.title_ok(ok), ok


def test_washed_out_frames_are_rejected():
    """🫥 إطار مغسول أبيض/سادة يترفض (زي ما شفناه في المراجعة البصرية)."""
    from engine import clips
    base = {"frames": 8, "texty": 0.0, "flatblk": 0.10, "flat": 0.5, "bright": 0.5, "sat": 60}
    assert clips.is_clean(dict(base))
    assert not clips.is_clean({**base, "bright": 0.97, "sat": 6})      # أبيض ميّت
    assert not clips.is_clean({**base, "sat": 2, "flatblk": 0.30})     # سادة رمادي
    assert clips.is_clean({**base, "bright": 0.93, "sat": 55})         # ثلج/سما فاتحة = تمام
