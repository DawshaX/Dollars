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
"""تعلّم حقيقي: قراءة أرقام يوتيوب بتوكن القناة (من غير مشروع جوجل جديد)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import analytics


def test_needs_key_or_token(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setattr(analytics, "_oauth_token", lambda: None)
    try:
        analytics.fetch_stats(["abc"])
        raised = False
    except RuntimeError as e:
        raised = "توكن" in str(e)
    assert raised, "لازم يقول إن المفتاح أو التوكن ناقص"


def test_uses_oauth_token_when_no_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setattr(analytics, "_oauth_token", lambda: "tok-123")
    seen = {}
    def fake_get(url, timeout=30, token=None):
        seen["url"], seen["token"] = url, token
        return {"items": [{"id": "abc", "statistics": {"viewCount": "7", "likeCount": "1"},
                           "snippet": {"title": "t"}}]}
    monkeypatch.setattr(analytics, "_get", fake_get)
    out = analytics.fetch_stats(["abc"])
    assert seen["token"] == "tok-123" and "key=" not in seen["url"]
    assert out["abc"]["views"] == 7


def test_sync_reports_reason_without_any_credential(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.setattr(analytics, "_oauth_token", lambda: None)
    r = analytics.sync(write=False)
    assert r["ok"] is False and "ناقص" in r["reason"]
