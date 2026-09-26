"""اختبارات المخزون المحلي وطبقة المراجع (بلا إنترنت)."""
import json, pathlib, sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import refs, sfx, stock


def test_sfx_pack_grew_and_all_sounds_exist():
    assert len(sfx.SFX) >= 60, "المخزون المحلي لازم يكون 60 مؤثر على الأقل"
    for name in ("shimmer", "vinyl", "fire_crackle", "ui_tick", "lullaby_note", "thunder_far"):
        assert name in sfx.SFX and sfx.render(name).size > 200
    # التوصيات بتشاور على المؤثرات الموجودة فعلًا
    for kind, names in sfx.RECOMMENDED.items():
        for n in names:
            assert n in sfx.SFX, f"{kind}: {n} مش موجود"


def test_uses_groups_cover_new_audio():
    for group in ("atmosphere", "magic", "ui_soft"):
        assert group in sfx.USES and len(sfx.USES[group]) >= 5
        for n in sfx.USES[group]:
            assert n in sfx.SFX


def test_stock_report_counts_local_assets():
    r = stock.report()
    assert r["sfx"] >= 60 and r["stickers"] >= 36 and r["memes"] >= 6
    assert r["visual_fx"] >= 10 and r["scenes"] >= 12
    assert r["total_assets"] >= 100
    assert isinstance(stock.text_report(), str) and "مخزون" in stock.text_report()


def test_refs_pinterest_links_are_safe_and_complete():
    links = refs.pinterest_links("kinetic sand")
    assert len(links) >= 5
    assert all(l["url"].startswith("https://www.pinterest.com/search/") for l in links)
    assert all(l["label"] for l in links)


def test_refs_views_parser_reads_youtube_formats():
    for txt, val in (("378,428,580 views", 378428580), ("1.2M views", 1_200_000),
                     ("556K views", 556_000), ("no views", 0)):
        assert refs._views_number(txt) == val


def test_refs_demand_and_apply_use_stored_trends(tmp_path, monkeypatch):
    monkeypatch.setattr(refs, "STATE", tmp_path)
    (tmp_path / "trends.json").write_text(json.dumps({"demand": {"sleep": 30, "story": 5}}), encoding="utf-8")
    assert refs.demand()["sleep"] == 30
    out = refs.apply_to_brain_from({"demand": {"sleep": 30, "story": 5}})
    assert "applied" in out            # مايفشلش أبدًا حتى لو مفيش عقل محفوظ


def test_board_document_marks_reference_only(tmp_path, monkeypatch):
    monkeypatch.setattr(refs, "STATE", tmp_path)
    monkeypatch.setattr(refs, "REFS", tmp_path / "refs")
    monkeypatch.setattr(refs, "_get", lambda url, timeout=20: b"")
    d = refs.board("rain on window", limit=2)
    assert d["pinterest"] and "ممنوع" in d["rule"]
    assert (tmp_path / "refs.json").exists()


def test_search_demand_parses_suggestions(monkeypatch):
    """اقتراحات البحث الحقيقية: بنسأل يوتيوب «الناس بتكتب إيه؟» بلا مفتاح."""
    import json as _json
    fake = _json.dumps(["rain sounds", ["rain sounds", "rain sounds for sleeping", "rain sounds no ads"]]).encode()
    monkeypatch.setattr(refs, "_get", lambda url, timeout=20: fake)
    got = refs.youtube_suggest("rain sounds")
    assert "rain sounds for sleeping" in got
    d = refs.search_demand()
    assert set(d["by_pillar"]) == {"sleep", "focus", "satisfying", "story"}
    assert d["by_pillar"]["sleep"]


def test_phrases_for_uses_stored_demand(tmp_path, monkeypatch):
    monkeypatch.setattr(refs, "STATE", tmp_path)
    (tmp_path / "trends.json").write_text(json.dumps(
        {"search_demand": {"by_pillar": {"sleep": ["rain sounds", "no ads"]}}}), encoding="utf-8")
    assert refs.phrases_for("sleep") == ["rain sounds", "no ads"]


def test_palette_and_split_tone_from_reference():
    """تحليل المراجع ⇒ لوحة ألوان ⇒ بتتطبّق فعلًا على الكادر."""
    import numpy as np
    from engine import grade
    img = np.linspace(0.05, 0.95, 48, dtype=np.float32)[None, :, None].repeat(3, 2).repeat(48, 0)
    cool = grade.split_tone(img, ["#0a1030", "#2a3a6b", "#9fc4ff"], strength=0.6)
    warm = grade.split_tone(img, ["#2b1408", "#a05a28", "#ffd9a0"], strength=0.6)
    cw = float((cool[:, :, 0] - cool[:, :, 2]).mean())
    ww = float((warm[:, :, 0] - warm[:, :, 2]).mean())
    assert cw < -0.02 and ww > 0.02, "اللوحة مش بتغيّر مزاج الألوان"
    assert float(warm.std()) > 0.1, "التدرّج ضاع بعد التطبيق"
