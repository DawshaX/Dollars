"""اختبارات الوكيل المراقب: يجيب أرقام · يكتب التحليل · يعلّم العقل."""
import json, pathlib, sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import agent, analytics


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(analytics, "STATE", tmp_path)
    monkeypatch.setattr(agent, "STATE", tmp_path)
    return tmp_path


def test_sync_without_videos_is_graceful(state):
    r = analytics.sync()
    assert r["ok"] is False and "منشورة" in r["reason"]


def test_sync_without_key_says_why(state, monkeypatch):
    monkeypatch.setattr(analytics, "key", lambda: None)
    (state / "published.json").write_text(json.dumps({"videos": [
        {"video_id": "abc", "title": "t", "features": {"pillar": "sleep"}}]}), encoding="utf-8")
    r = analytics.sync()
    assert r["ok"] is False and "YOUTUBE_API_KEY" in r["reason"]


def test_sync_writes_analytics_that_the_brain_can_learn_from(state, monkeypatch):
    (state / "published.json").write_text(json.dumps({"videos": [
        {"video_id": "v1", "title": "قديمة", "views": 100, "features": {"pillar": "sleep", "hour": 22}},
        {"video_id": "v2", "title": "تانية", "features": {"pillar": "satisfying", "hour": 9}}]}),
        encoding="utf-8")
    monkeypatch.setattr(analytics, "key", lambda: "k")
    monkeypatch.setattr(analytics, "fetch_stats", lambda ids, api_key=None: {
        "v1": {"title": "قديمة", "views": 250, "likes": 12, "comments": 3},
        "v2": {"title": "تانية", "views": 900, "likes": 40, "comments": 5}})
    monkeypatch.setattr(analytics, "channel_totals", lambda *a, **k: {"title": "Dollars", "subs": 10})
    r = analytics.sync()
    assert r["ok"] and r["videos"] == 2 and r["views_gained"] == 1050   # (250-100) + 900
    d = json.loads((state / "analytics.json").read_text(encoding="utf-8"))
    assert d["videos"][0]["features"]["pillar"] == "sleep"
    # العقل لازم يستفيد فورًا
    brain = agent.Brain()
    out = agent.learn(brain, analytics_path=str(state / "analytics.json"))
    assert out["learned"] == 2 and brain.meta["samples"] == 2
    assert brain.prior("pillar", "satisfying") > brain.prior("pillar", "sleep")   # اللي جاب أكتر اتعلّم


def test_report_lists_best_first(state):
    (state / "analytics.json").write_text(json.dumps({"synced_at": "2026-09-25T00:00:00Z", "videos": [
        {"title": "أ", "views": 10, "features": {"pillar": "sleep"}},
        {"title": "ب", "views": 900, "features": {"pillar": "satisfying"}}]}), encoding="utf-8")
    txt = analytics.report()
    table = txt.split("| الفيديو")[1]                     # نتأكد من ترتيب جدول الفيديوهات
    assert table.index("ب") < table.index("أ") and "satisfying" in txt
    assert txt.index("- **satisfying**") < txt.index("- **sleep**")   # الأفضل فوق
