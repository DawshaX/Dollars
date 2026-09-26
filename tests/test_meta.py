"""اختبارات محرّك البيانات الوصفية (يوتيوب من أ ل ي)."""
import json

import pytest

from engine import meta


def test_sleep_long_metadata_is_complete():
    md = meta.build({"pillar": "sleep", "kw": "Heavy Rain on Window", "hours": 10})
    assert len(md["titles"]) == 3
    assert all(len(t) <= 100 for t in md["titles"])
    assert md["kind"] == "long"
    assert md["chapters"] and md["chapters"][0] == "0:00 Start"
    assert 1 <= len(md["hashtags"]) <= 15
    assert sum(len(t) + 1 for t in md["tags"]) <= 500
    assert md["made_for_kids"] is False
    assert md["disclosure"]["altered_or_synthetic"] is True
    assert "Heavy Rain on Window" in md["description"]
    assert md["thumbnail_texts"] and len(md["thumbnail_texts"]) == 3
    assert meta.validate(md) == []


def test_shorts_metadata_gets_shorts_tag_and_no_chapters():
    md = meta.build({"pillar": "satisfying", "kw": "Kinetic Sand", "seconds": 30})
    assert md["kind"] == "short"
    assert md["chapters"] == []
    assert any("#shorts" in t for t in md["titles"])
    assert "#shorts" in md["hashtags"]


def test_story_metadata_uses_character_name():
    md = meta.build({"pillar": "story", "minutes": 2, "character": "Nono",
                     "thing": "the little rain cloud"})
    assert "Nono" in md["titles"][0]
    assert "disclosure" in md


def test_i18n_titles_for_world_channel():
    md = meta.build({"pillar": "sleep", "kw": "Rain Sounds", "hours": 8})
    assert len(md["title_i18n"]) >= 10
    assert any("\u0600" <= ch <= "\u06ff" for ch in md["title_i18n"]["ar"])   # فيه عربي
    assert md["title_i18n"]["en"].startswith("Rain Sounds")


def test_validation_catches_real_problems():
    bad = {"titles": ["x" * 130], "description": "قصير", "tags": [], "hashtags": ["#" + str(i) for i in range(20)],
           "kw": "rain", "kind": "long", "made_for_kids": True}
    problems = meta.validate(bad)
    txt = " | ".join(problems)
    assert "أطول من" in txt and "قصير جدًا" in txt and "مفيش وسوم" in txt
    assert "هاشتاج" in txt and "مصنوع للأطفال" in txt


def test_validation_catches_missing_disclosure():
    md = meta.build({"pillar": "sleep", "hours": 3})
    md["description"] = md["description"].replace("AI disclosure", "note").replace("generated", "made")
    assert any("إفصاح" in p for p in meta.validate(md))


def test_write_package_produces_files(tmp_path):
    md = meta.build({"pillar": "sleep", "kw": "Rain Sounds", "hours": 10})
    paths = meta.write_package(md, tmp_path)
    assert (tmp_path / "rain-sounds.meta.json").exists()
    txt = (tmp_path / "rain-sounds.meta.txt").read_text(encoding="utf-8")
    assert "العنوان (A)" in txt and "=== الوصف ===" in txt and "أول تعليق مثبّت" in txt
    assert json.loads((tmp_path / "rain-sounds.meta.json").read_text(encoding="utf-8"))["pillar"] == "sleep"


def test_smart_copy_merges_without_breaking_rules(monkeypatch):
    """الكوبي الذكي يزوّد عنوان/وسوم/ترجمات — ومن غير ما يكسر قواعد يوتيوب."""
    from engine import meta, copy as _copy
    monkeypatch.setattr(meta, "_smart", lambda spec: {
        "titles": ["Rain that Actually Helps You Sleep in Minutes"],
        "tags": ["rain sounds for sleeping no ads", "rain sounds 8 hours"],
        "description": "وصف ذكي " * 200,
        "hook": "Rain that actually helps",
        "localizations": {"es": {"title": "Lluvia para dormir", "description": "d"}},
        "suggests": ["rain sounds for sleeping no ads"],
    })
    md = meta.build({"pillar": "sleep", "kw": "Rain Sounds", "seconds": 60, "kind": "short"})
    assert md["titles"][0].startswith("Rain that Actually") and md["titles"][0].endswith("#shorts")
    assert "rain sounds for sleeping no ads" in md["tags"]
    assert sum(len(t) + 1 for t in md["tags"]) <= 500
    assert md["localizations"]["es"]["title"] == "Lluvia para dormir"
    assert md["hook"]
    assert ("disclos" in md["description"].lower()) or ("إفصاح" in md["description"]), "الإفصاح لازم يفضل موجود"
    assert md["search_demand"]
