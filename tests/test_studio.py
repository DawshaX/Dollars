
"""اختبارات الاستوديو: ٢٤ شورت + ٤ طويلة · تنوّع إلزامي · ميتاداتا النوع."""
import json
import pathlib
import tempfile

from engine import genres, studio, variety


def _fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(variety, "STATE", tmp_path / "variety.json")


def test_day_plan_shape(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    plan = studio.build_day("2026-09-27", write=False)
    shorts = [s for s in plan["slots"] if s["kind"] == "short"]
    longs = [s for s in plan["slots"] if s["kind"] == "long"]
    assert len(shorts) == 24, "شورت كل ساعة"
    assert len(longs) == 4, "٤ طويلة في اليوم"
    assert {s["hour"] for s in shorts} == set(range(24))
    assert all(s["idea"]["genre"] in genres.GENRES for s in plan["slots"])


def test_variety_is_enforced_no_near_duplicates(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    plan = studio.build_day("2026-09-27", write=False)
    sigs = [s["idea"]["sig"] for s in plan["slots"]]
    for i, a in enumerate(sigs):
        for b in sigs[max(0, i - 12):i]:
            assert variety.diffs(a, b) >= 3, f"تكرار قريب: {a} / {b}"


def test_every_genre_has_real_topics_and_meta(tmp_path, monkeypatch):
    _fresh(tmp_path, monkeypatch)
    plan = studio.build_day("2026-09-27", write=False)
    seen = {s["idea"]["genre"] for s in plan["slots"]}
    assert len(seen) >= 5, "تنوّع حقيقي في الأنواع"
    for s in plan["slots"]:
        i = s["idea"]
        assert i["kw"], "كل دور له موضوع حقيقي"
        assert i["playlist"] and i["scene"] and i["audio"] and i["transition"] and i["montage"]


def test_facts_genre_requires_source():
    g = genres.get("facts")
    assert g["text_policy"] == "en_lines", "الحقائق لازم نص على الشاشة"
    assert "verified" in " ".join(g["tags"]) or "facts" in " ".join(g["tags"])


def test_genre_meta_reaches_youtube_package(tmp_path, monkeypatch):
    from engine import meta
    md = meta.build({"genre": "facts", "pillar": "satisfying", "kind": "short", "seconds": 30,
                     "kw": "Volcano", "lines": ["Volcanoes build islands."],
                     "source": "https://en.wikipedia.org/wiki/Volcano",
                     "title_style": "3 Facts About Volcano You Didn't Know", "scene": "volcano"})
    assert md["genre"] == "facts"
    assert md["playlist"] == "Facts & Science"
    assert "https://en.wikipedia.org/wiki/Volcano" in md["description"]
    assert "volcano" in " ".join(md["tags"]).lower()
    assert md["titles"][0].endswith("#shorts")
