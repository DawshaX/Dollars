"""
🏭 المصنع — Dollars Studio
==========================
ده اللي **بيشغّل نفسه**: يقرأ خطة العقل → يختار الدور → يطلّع الفيديو كامل (مونتاج + صوت +
غلاف + بيانات) → ينشره لو القناة مربوطة، ولو لأ **يحفظه في الطابور** ويكمّل.

التشغيل:
    python engine/factory.py --hourly            # شورت واحد (اللي جاي في الخطة)
    python engine/factory.py --hourly --count 3  # تلاتة
    python engine/factory.py --daily             # طويل (نوم 3/8/10 ساعات) + قصة
    python engine/factory.py --status            # تقرير المصنع
    python engine/factory.py --kind story --count 1

كل حاجة بتتسجّل في: state/produced.json (السجل) · state/queue.json (جاهز للنشر) · state/factory_log.md

مبادئ ملزمة (زي ما اتفقنا):
- مفيش حاجة مسروقة: كل مشهد/صوت/ملصق ملكنا.
- الإفصاح عن AI إلزامي في كل وصف (meta.validate بيمنع النشر لو ناقص).
- النشر بلا حد: كل ساعة شورت + طويلة يوميًا (وبالزيادة عند تعدد المشاريع).
- الفشل ممنوع يوقّف الطابور: أي خطأ يتسجّل والمصنع يكمّل.
"""
from __future__ import annotations

import json
import pathlib
import random
import sys
import time
import traceback
from datetime import date, datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import agent, editor, meta, publish, visuals  # noqa: E402

QUEUE_CAP = 72                  # أقصى عدد وصفات محفوظة في الطابور
STATE = ROOT / "state"
WORK = ROOT / "work"


def _jload(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _jdump(p, obj):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _load_ledger() -> dict:
    return _jload(STATE / "produced.json", {"done": [], "stats": {}, "created": None}) or {"done": []}


def _save_ledger(led: dict):
    led["updated"] = datetime.now(timezone.utc).isoformat()
    _jdump(STATE / "produced.json", led)


def _plan(date_str: str | None = None) -> dict:
    """خطة اليوم من العقل (أو بيولّدها لو مش موجودة)."""
    date_str = date_str or date.today().isoformat()
    p = STATE / f"plan_{date_str}.json"
    plan = _jload(p)
    if not plan:
        brain = agent.Brain.load()
        plan = agent.plan_day(brain, date_str, characters=agent.load_characters().get("characters"))
        brain.save()
    return plan


def next_slots(kind: str = "short", count: int = 1, date_str: str | None = None) -> list:
    """أدوار لسه ما اتعملتش من خطة اليوم (شورت / طويل)."""
    plan = _plan(date_str)
    led = _load_ledger()
    done = {(d.get("date"), d.get("hour"), d.get("kind")) for d in led.get("done", [])}
    out = []
    for s in plan.get("slots", []):
        if s.get("kind") != kind:
            continue
        if (plan["date"], s["hour"], kind) in done:
            continue
        out.append(dict(s, date=plan["date"]))
        if len(out) >= count:
            break
    return out


def missed_slots(kind: str = "short", now=None) -> int:
    """كام دور فات في خطة النهاردة ولسه ما اتعملش (عشان الساعة لو اتأخرت ما تضيّعش حاجة)."""
    now = now or datetime.now(timezone.utc)
    plan = _plan()
    led = _load_ledger()
    done = {(d.get("date"), d.get("hour"), d.get("kind")) for d in led.get("done", [])}
    n = 0
    for sl in plan.get("slots", []):
        if sl.get("kind") != kind:
            continue
        if (plan["date"], sl["hour"], kind) in done:
            continue
        if int(sl.get("hour", 0)) <= now.hour or plan.get("date", "") < now.date().isoformat():
            n += 1
    return n


def produce(slot: dict, out_dir=None, seed: int | None = None) -> dict:
    """
    يطلّع الفيديو المطلوب حسب النوع: شورت مريح · أجواء · قصة · نوم طويل.
    """
    idea = slot.get("idea") or {}
    pillar = idea.get("pillar") or "satisfying"
    dur = idea.get("duration") or ""
    seed = seed if seed is not None else random.Random(f"{slot.get('date')}|{slot.get('hour')}").randint(1, 10**6)
    out_dir = pathlib.Path(out_dir or (WORK / f"{slot.get('date')}_{slot.get('hour'):02d}"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ed = editor.Editor(str(out_dir), seed=seed)
    # المرجع البصري (Pinterest/Openverse) بيحدّد المظهر والكاميرا والمشاهد — والموسيقى من صنعنا
    try:
        from engine import refs as refs_mod
        recipe = refs_mod.recipe_for(pillar)
    except Exception:
        recipe = {}
    style_kw = {k: recipe[k] for k in ("look", "moves", "scenes", "music") if recipe.get(k)}
    if slot.get("kind") == "long":         # الطويلة: المشهد هو اللي يحكم المظهر
        style_kw.pop("look", None); style_kw.pop("scenes", None)
    t0 = time.time()

    if slot.get("kind") == "long" and pillar in ("sleep", "focus"):
        hours = float(str(dur).replace("h", "") or 10)
        hours = hours if hours in (3, 8, 10, 2, 4, 6, 12) else 8
        scene = idea.get("scene") or "valley_lake"
        audio = random.Random(seed).choice(["calm_night", "sleep_rain", "ocean", "fireplace", "focus"])
        rec = ed.make("sleep_long", hours=hours, scene=scene, audio=audio, **style_kw)
        rec.update(pillar="sleep", duration=f"{int(hours)}h")
    elif pillar == "story":
        rec = ed.make("story_short", seconds=float(str(dur).replace("m", "") or 2) * 60)
        rec.update(pillar="story", duration=dur)
    elif pillar in ("focus", "sleep") or (slot.get("kind") == "short" and random.Random(seed).random() < 0.25):
        rec = ed.make("ambience_short", seconds=float(str(dur).replace("s", "") or 45), **style_kw)
        rec.update(pillar="focus", duration=dur)
    else:
        secs = float(str(dur).replace("s", "") or 30)
        rec = ed.make("satisfying_short", seconds=secs if 15 <= secs <= 60 else 30, **style_kw)
        rec.update(pillar="satisfying", duration=dur)

    rec["recipe"] = {k: recipe.get(k) for k in ("look", "moves", "scenes", "music", "mood", "matched")} if recipe else None
    rec["slot"] = slot
    rec["seconds_spent"] = round(time.time() - t0, 1)
    rec["seed"] = seed
    rec["produced_at"] = datetime.now(timezone.utc).isoformat()
    return rec


def publish_or_stage(rec: dict, force_stage: bool = False) -> dict:
    """
    ينشر لو القناة مربوطة، وإلا يحفظ في الطابور. بيرجّع سطر النتيجة.
    """
    md = rec.get("meta") or {}
    video = rec.get("video")
    if not video or not pathlib.Path(video).exists():
        return {"published": False, "reason": "مفيش فيديو"}

    if md:
        problems = meta.validate(md)
        serious = [p for p in problems if "إفصاح" in p or "كلمات" in p or "مصنوع للأطفال" in p]
        if serious:
            return {"published": False, "reason": f"الفحص رفض النشر: {serious}"}

    ok = publish.available()
    if ok["ok"] and not force_stage:
        try:
            res = publish.publish(video, md, thumb_path=rec.get("thumbnail"))
            return {"published": True, "video_id": res.get("id"), "url": res.get("url"),
                    "thumbnail": res.get("thumbnail"), "playlist": res.get("playlist")}
        except Exception as e:
            return {"published": False, "reason": f"الرفع فشل: {type(e).__name__}: {e}"}
    q = _jload(STATE / "queue.json", {"items": []}) or {"items": []}
    q["items"].append({
        "at": datetime.now(timezone.utc).isoformat(),
        "slot": rec.get("slot"), "seed": rec.get("seed"), "kind": rec.get("kind"),
        "title": (md.get("titles") or [pathlib.Path(video).stem])[0],
        "pillar": rec.get("pillar"), "duration": rec.get("duration"),
        "reason": ok["reason"] if not ok["ok"] else "تم التخطّي بأمر",
    })
    _jdump(STATE / "queue.json", q)
    return {"published": False, "staged": True, "reason": ok["reason"],
            "queue_length": len(q["items"])}


def render_queue(force_stage: bool = False, limit: int | None = None, out_dir=None) -> dict:
    """
    يعيد إنتاج كل حاجة في الطابور **بنفس الوصفة والبذرة** (نفس الفيديو بالظبط) وينشرها.
    مهيّأ لليوم اللي نربط فيه القناة: أمر واحد يحوّل الطابور لمحتوى منشور.
    """
    q = _jload(STATE / "queue.json", {"items": []}) or {"items": []}
    items = q["items"][:limit] if limit else list(q["items"])
    lines, done = [], 0
    for it in items:
        slot = it.get("slot")
        if not slot:
            continue
        try:
            rec = produce(slot, out_dir=out_dir, seed=it.get("seed"))
            res = publish_or_stage(rec, force_stage=force_stage)
            record(rec, res)
            done += 1
            lines.append(f"↻ {it.get('title')} → " + (f"نُشر {res.get('url')}" if res.get("published") else f"لسه في الطابور ({res.get('reason')})"))
            if res.get("published") and not force_stage:
                q["items"].remove(it)
        except Exception as e:
            lines.append(f"❌ فشل إعادة إنتاج «{it.get('title')}»: {type(e).__name__}: {e}")
    _jdump(STATE / "queue.json", q)
    _log(lines or ["الطابور فاضي — مفيش حاجة تعاد"])
    return {"processed": done, "remaining": len(q["items"]), "lines": lines}


def record(rec: dict, result: dict):
    led = _load_ledger()
    led.setdefault("done", []).append({
        "date": rec.get("slot", {}).get("date"), "hour": rec.get("slot", {}).get("hour"),
        "kind": rec.get("slot", {}).get("kind"), "pillar": rec.get("pillar"),
        "duration": rec.get("duration"), "scene": rec.get("scene"),
        "video": rec.get("video"), "title": ((rec.get("meta") or {}).get("titles") or [""])[0],
        "published": bool(result.get("published")), "url": result.get("url"),
        "reason": result.get("reason"), "seconds_spent": rec.get("seconds_spent"),
        "at": rec.get("produced_at"),
    })
    st = led.setdefault("stats", {})
    st["total"] = st.get("total", 0) + 1
    st["published"] = st.get("published", 0) + (1 if result.get("published") else 0)
    st["staged"] = st.get("staged", 0) + (1 if result.get("staged") else 0)
    st["by_pillar"] = st.get("by_pillar", {})
    st["by_pillar"][rec.get("pillar", "?")] = st["by_pillar"].get(rec.get("pillar", "?"), 0) + 1
    _save_ledger(led)
    return led


def _log(lines: list):
    p = STATE / "factory_log.md"
    old = p.read_text(encoding="utf-8") if p.exists() else "# 🏭 سجل المصنع\n"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    p.write_text(old.rstrip() + f"\n\n## {stamp}\n" + "\n".join(f"- {l}" for l in lines) + "\n",
                encoding="utf-8")


def run(kind: str = "short", count: int = 1, force_stage: bool = False, out_dir=None,
        catchup: bool = False, max_catchup: int = 4) -> dict:
    if catchup:
        miss = missed_slots(kind)
        # الشورتس: نعوّض لحد 4 في التشغيل الواحد · الطويلة: واحدة بالكتير (ثقيلة أوي)
        count = max(count, min(max_catchup, miss)) if kind == "short" else max(count, min(2, miss))
    slots = next_slots(kind, count)
    lines, results = [], []
    if catchup and count > 1:
        lines.append(f"⏱️ تعويض: النهاردة فيه {count} دور مستحق ⇒ بنطلّعهم كلهم")
    if not slots:
        lines.append(f"مفيش أدوار {kind} فاضلة في خطة النهاردة — العقل هيعمل خطة بكرة")
    for slot in slots:
        try:
            rec = produce(slot, out_dir=out_dir)
            res = publish_or_stage(rec, force_stage=force_stage)
            led = record(rec, res)
            results.append({"slot": f"{slot['date']} {slot['hour']:02d}:00", "pillar": rec.get("pillar"),
                            "duration": rec.get("duration"), "video": rec.get("video"),
                            "result": res, "total_done": led["stats"]["total"]})
            lines.append(f"{slot['date']} {slot['hour']:02d}:00 · {rec.get('pillar')} · "
                         f"{rec.get('duration')} · {pathlib.Path(str(rec.get('video'))).name} · "
                         + (f"نُشر: {res.get('url')}" if res.get("published") else f"في الطابور ({res.get('reason')})"))
        except Exception as e:
            lines.append(f"❌ {slot.get('date')} {slot.get('hour')}:00 — فشل: {type(e).__name__}: {e}")
            traceback.print_exc()
    _log(lines)
    return {"slots": len(slots), "results": results, "lines": lines}


def status() -> dict:
    led = _load_ledger()
    q = _jload(STATE / "queue.json", {"items": []}) or {"items": []}
    pub = publish.available()
    plan = _plan()
    done_today = [d for d in led.get("done", []) if d.get("date") == date.today().isoformat()]
    return {
        "plan_for": plan.get("date"), "planned_slots": len(plan.get("slots", [])),
        "done_total": led.get("stats", {}).get("total", 0),
        "published_total": led.get("stats", {}).get("published", 0),
        "staged_total": led.get("stats", {}).get("staged", 0),
        "done_today": len(done_today),
        "queue": len(q["items"]),
        "publishing": pub["reason"],
        "by_pillar": led.get("stats", {}).get("by_pillar", {}),
        "last": (led.get("done") or [{}])[-1],
    }


def report_text() -> str:
    s = status()
    lines = [
        "# 🏭 حالة المصنع — Dollars Studio", "",
        f"- خطة اليوم: **{s['planned_slots']}** دور · اتعمل النهاردة: **{s['done_today']}**",
        f"- الإجمالي: **{s['done_total']}** فيديو (منهم **{s['published_total']}** منشور · "
        f"**{s['staged_total']}** في الطابور)",
        f"- الطابور الجاهز للنشر: **{s['queue']}**",
        f"- النشر: {s['publishing']}",
        f"- التوزيع: {s['by_pillar'] or '—'}",
    ]
    if s.get("last"):
        lines.append(f"- آخر حاجة: {s['last'].get('title')} ({s['last'].get('pillar')})")
    return "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="مصنع Dollars")
    ap.add_argument("--hourly", action="store_true", help="شورت واحد على الخطة")
    ap.add_argument("--daily", action="store_true", help="طويل نوم + قصة")
    ap.add_argument("--kind", choices=["short", "long"], default=None)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--catchup", action="store_true",
                    help="يعوّض الأدوار اللي فاتت في خطة النهاردة (لو الساعة اتأخرت)")
    ap.add_argument("--force-stage", action="store_true", help="ما تنشرش حتى لو القناة مربوطة")
    ap.add_argument("--out", default=None)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--render-queue", action="store_true", help="يعيد إنتاج الطابور وينشره (لبعد ربط القناة)")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    if a.status:
        print(report_text())
        return 0
    if a.render_queue:
        out = render_queue(force_stage=a.force_stage, limit=a.limit, out_dir=a.out)
        for line in out["lines"]:
            print("•", line)
        print(f"\nاتنفّذ: {out['processed']} · فاضل في الطابور: {out['remaining']}")
        return 0 if out["processed"] else 1
    kinds = []
    if a.daily:
        kinds = [("long", max(1, a.count))]
        if _jload(STATE / "queue.json") is not None and not a.kind:
            kinds.append(("story", 1))
    elif a.hourly:
        kinds = [("short", max(1, a.count))]
    elif a.kind:
        kinds = [(a.kind, max(1, a.count))]
    else:
        kinds = [("short", 1)]
    total = 0
    for kind, cnt in kinds:
        out = run(kind, cnt, force_stage=a.force_stage, out_dir=a.out, catchup=a.catchup)
        total += out["slots"]
        for line in out["lines"]:
            print("•", line)
    print("\n" + report_text())
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
