#!/usr/bin/env python3
"""
🔎 تحقّق المشاريع — يتأكد إن كل مشروع جوجل مضبوط فعلاً على **قناتنا** قبل ما ننشر بيه.

ليه ده مهم؟ لو اعتماد مشروع تاني بيفتح قناة تانية، النشر بيه = فيديوهات على القناة الغلط.
القاعدة عندنا: **مفيش مشروع يتستخدم غير لما القناة اللي بيرجعها جوجل تكون نفس قناتنا.**

بيحفظ النتيجة في state/youtube_projects.json والمصنع بيقراه في اختيار المشروع.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import publish  # noqa: E402

STATE = pathlib.Path("state/youtube_projects.json")
MAIN_CHANNEL_FILE = pathlib.Path("state/channel.json")


def main_channel() -> str:
    try:
        return json.loads(MAIN_CHANNEL_FILE.read_text(encoding="utf-8")).get("id", "")
    except Exception:
        return "UCG9g_26H65D3FahqyiYPHAw"


def check(project: int, c: dict) -> dict:
    out = {"project": project, "configured": bool(all((c["client_id"], c["client_secret"], c["refresh_token"])))}
    if not out["configured"]:
        return out
    try:
        tok = publish.access_token(c)
        ch = publish.my_channel(tok)
        out.update({"ok": True, "channel_id": ch["id"], "channel_title": ch["title"]})
    except Exception as e:
        out.update({"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})
    return out


def main() -> int:
    main_cid = main_channel()
    report = {"main_channel": main_cid, "checked_at": publish.datetime.now(publish.timezone.utc).isoformat(), "projects": {}}
    print(f"🎯 قناتنا: {main_cid}")
    for i in range(1, 5):
        r = check(i, publish.creds(i))
        report["projects"][str(i)] = r
        if not r["configured"]:
            print(f"  • مشروع {i}: ⚪ مش مضبوط")
        elif r.get("ok") and r.get("channel_id") == main_cid:
            print(f"  • مشروع {i}: ✅ {r['channel_title']} — ينفع للنشر (+٦ رفعات/يوم)")
        elif r.get("ok"):
            print(f"  • مشروع {i}: 🚫 قناة تانية ({r.get('channel_id')}) — مش هنستخدمه")
        else:
            print(f"  • مشروع {i}: ❌ {r.get('error')}")
    usable = [k for k, v in report["projects"].items() if v.get("ok") and v.get("channel_id") == main_cid]
    report["usable"] = usable
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💪 مشاريع مؤهلة للنشر: {usable} ⇒ سقف ~{len(usable) * publish.DAILY_UPLOADS_PER_PROJECT} رفعة/يوم")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
