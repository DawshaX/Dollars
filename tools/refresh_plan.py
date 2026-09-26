#!/usr/bin/env python3
"""🗓️ يبني خطة الاستوديو (٢٤ شورت + ٤ طويلة) للنهاردة وبكرة ويحدّث الطابور من غير تكرار."""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import studio  # noqa: E402

Q = pathlib.Path("state/queue.json")


def load() -> dict:
    try:
        return json.loads(Q.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}


def main() -> int:
    q = load()
    have = {(i.get("slot", {}).get("date"), i.get("slot", {}).get("hour"),
             i.get("slot", {}).get("kind")) for i in q.get("items", [])}
    today = datetime.now(timezone.utc).date()
    added = 0
    for d in (today, today + timedelta(days=1), today + timedelta(days=2)):
        plan = studio.build_day(d.isoformat())
        print(f"📋 {d}: {plan['shorts']} شورت · {len(plan['longs'])} طويلة · {json.dumps(plan['mix'], ensure_ascii=False)}")
        for s in plan["slots"]:
            k = (plan["date"], s["hour"], s["kind"])
            if k in have:
                continue
            i = s["idea"]
            q.setdefault("items", []).append({
                "title": f"[{i['genre_ar']}] {i['kw']} · {i['duration']}",
                "slot": {**s, "date": plan["date"]}, "seed": s.get("seed"),
                "added": datetime.now(timezone.utc).isoformat()})
            have.add(k)
            added += 1
    q["studio"] = True
    q["updated"] = datetime.now(timezone.utc).isoformat()
    Q.write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ الطابور: {len(q['items'])} عنصر (زاد {added})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
