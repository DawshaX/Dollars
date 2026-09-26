"""♾️ اختبارات المخزون اللانهائي — المساحة حقيقية ومفيش تكرار ومفيش قيمة وهمية."""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import music, unlimited as U, visuals  # noqa: E402

PILLARS = ["satisfying", "sleep", "focus", "story"]


def test_space_is_really_huge_for_every_pillar():
    for p in PILLARS:
        n = U.space_size(p)
        assert n > 1_000_000, f"مساحة {p} صغيرة: {n}"


def test_combo_is_deterministic_and_complete():
    for p in PILLARS:
        a, b = U.combo(12345, p), U.combo(12345, p)
        assert a == b, "نفس الرقم لازم يطلع نفس التركيبة"
        assert a["scenes"] and 3 <= len(a["scenes"]) <= 6
        assert a["music"] in music.STYLES()
        assert len(a["palette"]) == 3 and all(x.startswith("#") for x in a["palette"])
        assert a["transition"] in ("crossfade", "fade")
        assert 0.2 <= float(a["palette_strength"]) <= 0.7


def test_no_repeats_over_many_videos():
    for p in PILLARS:
        slots = [U.slot(i, p) for i in range(5000)]
        assert len(set(slots)) == len(slots), f"فيه تكرار في {p}"


def test_next_combo_advances_and_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "STATE", tmp_path / "unlimited.json")
    first = U.next_combo("satisfying")
    second = U.next_combo("satisfying")
    assert first["combo_id"] != second["combo_id"]
    saved = json.loads((tmp_path / "unlimited.json").read_text(encoding="utf-8"))
    assert saved["index"] == 2 and len(saved["used"]) == 2


def test_enrich_variates_every_video_and_stays_valid(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "STATE", tmp_path / "u.json")
    base = {"scenes": ["sand_table", "fireplace"], "look": "cinema_warm",
            "music": "lofi_keys", "palette": ["#111111", "#222222", "#333333"]}
    combos, musics, moves = set(), set(), set()
    for _ in range(12):
        kw = U.enrich(dict(base), "satisfying")
        assert kw["scenes"] and all(s in visuals.SCENES for s in kw["scenes"]), "مشهد غير موجود"
        assert len(kw["scenes"]) <= 6
        assert kw["music"] in music.STYLES()
        assert kw["transition"] in ("crossfade", "fade")
        assert kw["unlimited"]["space_size"] > 1_000_000
        combos.add(kw["unlimited"]["combo_id"])
        musics.add(kw["music"])
        moves.add(tuple(kw["moves"]))
    assert len(combos) == 12, "المصنع ما بيجددش التركيبة كل فيديو"
    assert len(musics) >= 3, "الموسيقى مش بتتنوّع"
    assert len(moves) >= 4, "حركات الكاميرا مش بتتنوّع"


def test_stats_reports_base_and_space():
    s = U.stats()
    assert s["used_total"] >= 0
    assert s["base_stock"]["sfx"] >= 40 and s["base_stock"]["music"] >= 6
    assert s["base_stock"]["scenes"] >= 10 and s["base_stock"]["looks"] >= 4
