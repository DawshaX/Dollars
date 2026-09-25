"""اختبارات العقل الذاتي: بيتعلّم من الأرقام · بيولّد أفكار · بيخترع شخصيات · بيخطط."""
import json

import pytest

from engine import agent


def test_bootstrap_priors_without_data():
    b = agent.Brain()          # عقل جديد
    b._bootstrap()
    assert b.prior("pillar", "sleep") > b.prior("pillar", "focus")     # من بحثنا
    assert b.meta["samples"] == 0


def test_brain_learns_what_wins():
    b = agent.Brain(); b._bootstrap()
    good = {"features": {"pillar": "sleep", "scene": "black", "duration": "10h", "thumb": "شاشة سوداء + نص واضح"},
            "views": 4_000_000, "retention": 0.55, "likes": 90_000, "comments": 1200, "subs": 9000}
    bad = {"features": {"pillar": "story", "scene": "harmonograph", "duration": "2m", "thumb": "وش متعجّب"},
           "views": 3_000, "retention": 0.20, "likes": 30, "comments": 1, "subs": 2}
    before = b.prior("pillar", "sleep")
    for _ in range(25):
        b.observe(good); b.observe(bad)
    assert b.prior("pillar", "sleep") > before
    assert b.prior("pillar", "sleep") > b.prior("pillar", "story")
    assert b.n("pillar", "sleep") == 25 and b.meta["samples"] == 50


def test_self_tuning_changes_learning_parameters():
    b = agent.Brain(); b._bootstrap()
    lr0, eps0 = b.meta["lr"], b.meta["eps"]
    for i in range(20):        # نتائج عشوائية بعيدة عن التوقّع ⇒ لازم يستكشف أكتر
        b.observe({"features": {"pillar": "sleep"},
                   "views": 10 ** (i % 7), "retention": (i % 10) / 10, "likes": 0})
    assert b.meta["eps"] != eps0 and b.meta["lr"] != lr0
    assert 0.05 <= b.meta["lr"] <= 0.9 and 0.05 <= b.meta["eps"] <= 0.45


def test_ideas_are_unique_ranked_and_counted():
    b = agent.Brain(); b._bootstrap()
    ideas = agent.collect_ideas(b, n=18, date_str="2026-09-25", characters=[])
    assert len(ideas) == 18
    sigs = [i["signature"] for i in ideas]
    assert len(set(sigs)) == 18
    assert all(ideas[i]["predicted"] >= ideas[i + 1]["predicted"] for i in range(len(ideas) - 1))
    assert all(i["kind"] in ("short", "long") for i in ideas)
    assert all(i["pillar"] in agent.PILLARS for i in ideas)


def test_no_repeat_of_used_ideas():
    b = agent.Brain(); b._bootstrap()
    a = agent.collect_ideas(b, n=10, date_str="2026-09-25", characters=[])
    c = agent.collect_ideas(b, n=10, date_str="2026-09-25", characters=[])
    assert not ({i["signature"] for i in a} & {i["signature"] for i in c})


def test_characters_are_new_original_and_visual(tmp_path):
    b = agent.Brain(); b._bootstrap()
    path = tmp_path / "characters.json"
    path.write_text(json.dumps({"characters": [{"id": "nono", "name": "Nono"}]}, ensure_ascii=False),
                    encoding="utf-8")
    made = agent.spawn_characters(b, n=4, path=path)
    assert len(made) == 4
    names = [c["name"] for c in made]
    assert len(set(names)) == 4
    for c in made:
        assert c["name"].lower() not in agent.BLOCK
        assert c["image_prompt"] and "no text" in c["image_prompt"]
        assert "بلا أي شبه" in c["look"]
        assert c["id"].endswith("_auto")
        assert agent._dist(c["name"].lower(), "nono") >= 3
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved["characters"]) == 5


def test_plan_day_has_24_shorts_and_longs(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "STATE", tmp_path)
    b = agent.Brain(); b._bootstrap()
    plan = agent.plan_day(b, "2026-09-25", characters=[])
    assert plan["shorts"] == 24
    assert 1 <= plan["longs"] <= 6
    assert (tmp_path / "plan_2026-09-25.json").exists()
    assert len(plan["slots"]) == plan["shorts"] + plan["longs"]
    hours = sorted(s["hour"] for s in plan["slots"] if s["kind"] == "long")
    assert hours == sorted(set(hours))


def test_daily_run_writes_state_and_report(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "STATE", tmp_path)
    monkeypatch.setattr(agent, "CONTENT", tmp_path)
    (tmp_path / "characters.json").write_text('{"characters": []}', encoding="utf-8")
    out = agent.run_daily("2026-09-25")
    assert out["ideas"] >= 20 and out["plan"]["shorts"] == 24
    assert (tmp_path / "ideas.json").exists() and (tmp_path / "brain.json").exists()
    rep = (tmp_path / "daily_report.md").read_text(encoding="utf-8")
    assert "🏆" in rep and "🗓️" in rep and "🔒" in rep
    assert "مفيش سرقة ولا حقوق" in rep


def test_learn_reads_analytics_file(tmp_path):
    b = agent.Brain(); b._bootstrap()
    p = tmp_path / "analytics.json"
    p.write_text(json.dumps({"videos": [
        {"title": "rain 10h", "views": 2_000_000, "retention": 0.5, "likes": 40000, "subs": 3000,
         "features": {"pillar": "sleep", "duration": "10h"}},
        {"title": "story", "views": 2_000, "retention": 0.2, "likes": 10, "subs": 1,
         "features": {"pillar": "story", "duration": "2m"}},
    ]}, ensure_ascii=False), encoding="utf-8")
    res = agent.learn(b, p)
    assert res["learned"] == 2
    assert b.prior("duration", "10h") > b.prior("duration", "2m")


def test_learn_without_data_is_honest(tmp_path):
    b = agent.Brain(); b._bootstrap()
    res = agent.learn(b, tmp_path / "nothing.json")
    assert res["learned"] == 0 and "لسه مفيش أرقام" in res["note"]
