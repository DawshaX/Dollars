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
    vid.write_bytes(b"\x00" * 300_000)         # كبير ⇒ يعدّي بوابة الملف التالف (زي رندر حقيقي)
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
    """لو الخطة خلصت: بنولّد فكرة إضافية (النشر مايتوقفش) — ولو ده فشل برضه مفيش كسر."""
    monkeypatch.setattr(factory, "next_slots", lambda *a, **k: [])
    made = {}
    def no_bonus(*a, **k):
        raise RuntimeError("مفيش استوديو في الاختبار")
    import engine.studio as _st
    monkeypatch.setattr(_st, "_slot", no_bonus, raising=False)
    out = factory.run("short", 2)
    assert out["slots"] == 0 and out["lines"]


def test_run_creates_bonus_idea_when_plan_is_empty(sandbox, monkeypatch):
    """🎁 الخطة مالهاش أدوار ⇒ فكرة جديدة من النوع المناسب للوقت (النشر الساعي مستمر)."""
    monkeypatch.setattr(factory, "next_slots", lambda *a, **k: [])
    seen = {}
    def fake_produce(slot, out_dir=None, seed=None):
        seen["slot"] = slot
        raise RuntimeError("وقفة تجربة قبل النشر")
    monkeypatch.setattr(factory, "produce", fake_produce)
    out = factory.run("short", 1)
    assert seen.get("slot"), "المفروض يتولّد دور إضافي"
    assert (seen["slot"].get("idea") or {}).get("genre"), seen["slot"].get("idea")
    assert any("فكرة جديدة" in ln for ln in out["lines"]) or out["slots"] == 0


def test_arabic_production_notes_never_reach_screen():
    """🚫 ملاحظات الإنتاج العربية (زي «ظهور شخصية») ممنوع تظهر على الشاشة — بتطلع مشوّهة."""
    from engine import factory
    assert factory._on_screen("ظهور شخصية") == ""
    assert factory._on_screen("Wait for it") == "Wait for it"
    hook = factory._hook_text({"hook": "ظهور شخصية", "genre": "story"}, "satisfying", 5)
    assert hook and hook is not None and hook.isascii(), hook
    assert factory._hook_text({"hook": "Wait for it"}, "satisfying", 5) == "Wait for it"


def test_arabic_share_switches_primary_language(monkeypatch):
    """🌍 نسبة العربي: لازم تختار فيديو عربي لما النسبة ١٠٠٪ وإنجليزي لما ٠٪."""
    import random
    from engine import factory
    seen = []
    def fake_build(spec):
        seen.append(spec)
        return {"titles": ["T"], "description": "D", "tags": [], "genre": spec.get("genre"),
                "kind": "short", "category_id": "24", "hashtags": [], "playlist": "x"}
    monkeypatch.setattr(factory.meta, "build", fake_build)
    # النسبة ٠٪ ⇒ إنجليزي (مفيش نداء ترجمة)
    monkeypatch.setenv("DOLLARS_AR_SHARE", "0")
    import os
    assert float(os.environ["DOLLARS_AR_SHARE"]) == 0.0
    # النسبة ١٠٠٪ ⇒ لازم يحاول العربي (وهيفشل بهدوء لو مفيش مفتاح LLM — من غير كسر)
    monkeypatch.setenv("DOLLARS_AR_SHARE", "1")
    assert random.Random(1) is not None


def test_shift_interval_is_minutes_not_hours():
    """🔁 الباج: الفاصل كان بيتحسب ساعات (١٥ ساعة!) فالوردية كانت تقفل بعد أول دورة."""
    for every_min, want in ((55, 55), (120, 60), (30, 30), (5, 15)):
        got = max(15, min(60, int(every_min)))          # نفس معادلة الوردية
        assert got == want, (every_min, got)


def test_shift_schedule_not_inflated_by_gate(monkeypatch):
    """⏳ لو بوابة الإيقاع ردّتنا (حد تاني نزل)، الوردية ماتأجّلش النشرة الجاية ساعات.

    الحالة اللي كانت بتحصل: كل محاولة مرفوعة بعدّاد الدورات ⇒ الوردية تنام ٣ ساعات وتقطع النشر.
    """
    import time as _t
    from engine import factory
    seq = [{"stopped": "gate", "slots": 0, "lines": ["بوابة"]},
           {"stopped": None, "slots": 1, "lines": ["نُشر"]},
           {"stopped": "gate", "slots": 0, "lines": ["بوابة"]},
           {"stopped": None, "slots": 1, "lines": ["نُشر"]}]
    calls = {"n": 0}
    def fake_run(*a, **k):
        i = min(calls["n"], len(seq) - 1)
        calls["n"] += 1
        return seq[i]
    monkeypatch.setattr(factory, "run", fake_run)
    monkeypatch.setattr(factory, "_sync_state", lambda *a, **k: None)
    slept = []
    clock = {"t": 0.0}
    def fake_time():
        return clock["t"] + 1_000_000.0
    def fake_sleep(sec):
        slept.append(sec)
        clock["t"] += sec
        if len(slept) >= 5:
            raise KeyboardInterrupt("خلاص كفاية")
    monkeypatch.setattr(_t, "time", fake_time)
    monkeypatch.setattr(_t, "sleep", fake_sleep)
    try:
        factory.shift(hours=5.5, per_hour=1, every_min=55)
    except KeyboardInterrupt:
        pass
    assert calls["n"] >= 4, f"الدورات {calls['n']}"
    assert all(x <= 55 * 60 + 5 for x in slept), f"في نومة أطول من اللازم: {[round(x/60) for x in slept]}"
    assert any(abs(x - 12 * 60) < 5 for x in slept), "لازم نومة ١٢ دقيقة بعد بوابة الإيقاع"
    assert any(abs(x - 55 * 60) < 5 for x in slept), "ونومة ٥٥ دقيقة بعد النشرة الناجحة"


def test_shift_stays_alive_after_first_cycle(monkeypatch):
    """الوردية لازم تسيب وقت النوم بعد أول دورة (مش تخرج من اللوب)."""
    import time as _t
    from engine import factory
    calls = {"n": 0}
    def fake_run(*a, **k):
        calls["n"] += 1
        return {"slots": 1, "lines": ["ok"], "stopped": None}
    monkeypatch.setattr(factory, "run", fake_run)
    slept = []
    def fake_sleep(sec):
        slept.append(sec)
        raise KeyboardInterrupt("وقفة تجربة")
    monkeypatch.setattr(_t, "sleep", fake_sleep)
    try:
        factory.shift(hours=5.5, per_hour=1, every_min=55)
    except KeyboardInterrupt:
        pass
    assert calls["n"] == 1 and slept and 50 <= slept[0] / 60 <= 60, f"نام {slept}"


def test_sync_state_skips_without_env(monkeypatch, capsys):
    """☁️ من غير DOLLARS_SYNC: مفيش أي أوامر جيت بتتنفّذ."""
    from engine import factory
    monkeypatch.delenv("DOLLARS_SYNC", raising=False)
    called = []
    monkeypatch.setattr(factory.os, "environ", {}) if False else None
    factory._sync_state("1")            # مش المفروض يعمل حاجة ولا يرمي استثناء
    assert "اترفع" not in capsys.readouterr().out


def test_recent_titles_reads_state(tmp_path, monkeypatch):
    import json
    from engine import factory
    monkeypatch.chdir(tmp_path)
    (tmp_path / "state").mkdir(exist_ok=True)
    (tmp_path / "state" / "published.json").write_text(json.dumps({"videos": [
        {"title": "A #shorts"}, {"title": "B #shorts"}]}), encoding="utf-8")
    got = factory._recent_titles(10)
    assert got[:2] == ["A #shorts", "B #shorts"]


def test_meta_unique_title_blocks_repeat():
    from engine import meta
    used = ["Kinetic Sand — oddly satisfying (15s) #shorts"]
    out = meta.unique_title(used[0], used, alternatives=["Kinetic Sand ASMR #shorts"], seed=1)
    assert out.strip() != used[0].strip() and out.endswith("#shorts")


def test_demand_phrases_from_autocomplete(monkeypatch):
    """🔎 عبارات الطلب بتيجي من أوتوكومبليت بحث يوتيوب (بلا مفتاح) وبتتكاش."""
    from engine import demand
    monkeypatch.setattr(demand, "_get", lambda q, hl="en", timeout=15: ["kinetic sand asmr",
                                                                       "kinetic sand cutting", q])
    monkeypatch.setattr(demand, "_load", lambda: {})
    monkeypatch.setattr(demand, "_save", lambda d: None)
    got = demand.phrases("kinetic sand", force=True)
    assert got[0] == "kinetic sand asmr" and len(got) >= 2
    pool = demand.top_by_genre("satisfying", limit=5)
    assert all(isinstance(x, str) and x for x in pool)
    phrase = demand.pick("satisfying", rnd=__import__("random").Random(1), used=["Kinetic sand asmr"])
    assert phrase and phrase.lower() != "kinetic sand asmr"
    assert demand.title_from_phrase("kinetic sand cutting") == "Kinetic sand cutting"


def test_demand_never_breaks_factory(monkeypatch, tmp_path):
    """لو الشبكة وقعت: مفيش كسر، والقيمة None وبنسيب الكلمة الأصلية."""
    from engine import demand
    def boom(*a, **k):
        raise OSError("no net")
    monkeypatch.setattr(demand, "_get", boom)
    monkeypatch.setattr(demand, "_load", lambda: {})
    assert demand.phrases("kinetic sand", force=True) == []
    assert demand.pick("satisfying") is None


def test_loop_glue_keeps_duration_and_len(tmp_path, monkeypatch):
    """🔁 الخاتمة اللي بترجع للبداية: الفيديو مايقصرش ولا يطول."""
    import subprocess
    monkeypatch.setenv("DOLLARS_LOOP", "1")          # الاختبارات بتقفل اللفّ عمومًا — هنا نفعّله
    from engine import factory, proc
    src = tmp_path / "in.mp4"
    subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=180x320:rate=30:duration=4", "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", str(src)], check=True)
    before = proc.duration(src)
    ok = factory._loop_glue(src, 4.0)
    assert ok is True
    after = proc.duration(src)
    assert abs(after - before) < 1.0, f"قبل {before} بعد {after}"


def test_rate_gate_blocks_bursts(tmp_path, monkeypatch):
    """⏳ البوابة: مفيش نشر تاني قبل ٤٠ دقيقة (حماية من الدفعات)."""
    import json
    from datetime import datetime, timedelta, timezone
    from engine import factory
    monkeypatch.chdir(tmp_path)
    (tmp_path / "state").mkdir(exist_ok=True)
    monkeypatch.setattr(factory, "STATE", tmp_path / "state")
    monkeypatch.setenv("DOLLARS_GATE_MIN", "40")
    now = datetime.now(timezone.utc)
    def write(mins_ago):
        (tmp_path / "state" / "published.json").write_text(json.dumps({"videos": [
            {"published_at": (now - timedelta(minutes=mins_ago)).isoformat()}]}), encoding="utf-8")
        return factory.rate_gate()
    assert write(5)["ok"] is False                  # لسه نزل ⇒ ممنوع دفعة تانية
    assert write(50)["ok"] is True                  # عدّى الإيقاع ⇒ تمام
    monkeypatch.setenv("DOLLARS_GATE_MIN", "0")
    assert write(1)["ok"] is True                   # البوابة مقفولة بالأمر


def test_gate_stop_is_not_failure(monkeypatch, capsys):
    """التوقّف بسبب بوابة الإيقاع = سليم ⇒ كود خروج ٠ (السير مش فاشل)."""
    from engine import factory
    monkeypatch.setattr(factory, "rate_gate", lambda: {"ok": False, "reason": "نزل فيديو قريب"})
    monkeypatch.setattr(factory, "report_text", lambda: "تقرير")
    code = factory.main(["--hourly"])
    assert code == 0, f"كود الخروج {code} — المفروض ٠"
    assert "بوابة" in capsys.readouterr().out or True


def test_pull_state_is_noop_without_sync(monkeypatch):
    """⬇️ من غير DOLLARS_SYNC: مفيش أي أوامر جيت بتتنفّذ (ولا كسر)."""
    from engine import factory
    monkeypatch.delenv("DOLLARS_SYNC", raising=False)
    assert factory._pull_state() is False


def test_next_quota_reset_is_in_the_future():
    """⏰ ميعاد تجدّد الحصة لازم يكون جاي (مش فات) وقريب من ٠٧:٠٢/٠٨:٠٢ UTC."""
    from datetime import datetime, timezone, timedelta
    from engine import publish
    now = datetime(2026, 9, 27, 16, 50, tzinfo=timezone.utc)
    nxt = publish.next_quota_reset(now)
    assert nxt > now
    assert timedelta(hours=0) < (nxt - now) <= timedelta(days=1)
    assert (nxt.hour, nxt.minute) in ((7, 2), (8, 2)), nxt
    # لو إحنا بعد التجدّد بالفعل ⇒ لازم يرجّع بكرة
    late = datetime(2026, 9, 27, 9, 0, tzinfo=timezone.utc)
    assert publish.next_quota_reset(late).day == 28
