"""اختبارات المصنع: خطة · إنتاج · طابور · سجل · تقرير (من غير شبكة)."""
import json

import pytest

from engine import agent, factory


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(factory, "STATE", tmp_path)
    monkeypatch.setattr(factory, "WORK", tmp_path / "work")
    monkeypatch.setattr(agent, "STATE", tmp_path)
    return tmp_path


def test_plan_is_generated_and_has_slots(sandbox):
    plan = factory._plan("2026-09-26")
    assert plan["shorts"] == 24 and plan["slots"]
    assert (sandbox / "plan_2026-09-26.json").exists()


def test_next_slots_skips_done(sandbox):
    slots = factory.next_slots("short", 3, "2026-09-26")
    assert len(slots) == 3 and all(s["kind"] == "short" for s in slots)
    factory._jdump(sandbox / "produced.json", {"done": [
        {"date": slots[0]["date"], "hour": slots[0]["hour"], "kind": "short"}], "stats": {}})
    again = factory.next_slots("short", 3, "2026-09-26")
    assert slots[0]["hour"] not in [s["hour"] for s in again]


def _good_rec(sandbox, hour=3, seed=999):
    """فيديو وهمي + بيانات كاملة تعدّي الفحص (زي اللي المصنع بيطلّعه فعلًا)."""
    from engine import meta
    vid = sandbox / "clip.mp4"
    vid.write_bytes(b"\x00" * 2048)
    return {"video": str(vid), "meta": meta.build({"pillar": "sleep", "kw": "Rain Sounds",
                                                   "hours": 8, "kind": "long"}),
            "thumbnail": None, "pillar": "sleep", "duration": "8h", "seed": seed,
            "kind": "sleep_long", "slot": {"date": "2026-09-26", "hour": hour, "kind": "long"}}


def test_publish_or_stage_without_token_queues(sandbox):
    rec = _good_rec(sandbox, hour=3)
    res = factory.publish_or_stage(rec)
    assert res["published"] is False and res["staged"] is True
    q = json.loads((sandbox / "queue.json").read_text(encoding="utf-8"))
    assert len(q["items"]) == 1 and q["items"][0]["slot"]["hour"] == 3
    assert "طابور" in res["reason"] or "توكن" in res["reason"]


def test_queue_keeps_recipe_for_later_publish(sandbox):
    rec = _good_rec(sandbox, hour=5, seed=12345)
    factory.publish_or_stage(rec)
    item = json.loads((sandbox / "queue.json").read_text(encoding="utf-8"))["items"][0]
    assert item["seed"] == 12345 and item["slot"]["hour"] == 5


def test_meta_validation_blocks_bad_metadata(sandbox):
    vid = sandbox / "clip.mp4"
    vid.write_bytes(b"\x00" * 64)
    md = {"titles": ["قصير"], "description": "بدون إفصاح", "tags": [], "hashtags": [],
          "kw": "rain", "kind": "long", "made_for_kids": False}
    rec = {"video": str(vid), "meta": md, "thumbnail": None, "slot": {}, "pillar": "sleep"}
    res = factory.publish_or_stage(rec)
    assert res["published"] is False and "الفحص رفض" in res["reason"]


def test_record_updates_stats_and_log(sandbox):
    rec = {"slot": {"date": "2026-09-26", "hour": 1, "kind": "short"}, "pillar": "satisfying",
           "duration": "30s", "scene": "sand_table", "video": "v.mp4",
           "meta": {"titles": ["عنوان"]}, "produced_at": "2026-09-26T00:00:00Z", "seconds_spent": 12}
    led = factory.record(rec, {"published": False, "staged": True, "reason": "في الطابور"})
    assert led["stats"]["total"] == 1 and led["stats"]["staged"] == 1
    assert led["stats"]["by_pillar"]["satisfying"] == 1
    assert led["done"][0]["title"] == "عنوان"


def test_status_report_is_honest(sandbox):
    s = factory.status()
    assert s["done_total"] == 0 and s["queue"] == 0
    txt = factory.report_text()
    assert "حالة المصنع" in txt and "النشر:" in txt


def test_run_without_slots_logs_and_returns(sandbox, monkeypatch):
    monkeypatch.setattr(factory, "next_slots", lambda *a, **k: [])
    out = factory.run("short", 2)
    assert out["slots"] == 0 and out["lines"]
