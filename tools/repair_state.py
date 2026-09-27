#!/usr/bin/env python3
"""
🛠️ مُصلّح حالة المصنع — Dollars Studio
=====================================
ليه؟ لأن ملفات الحالة (JSON) بتتكتب من أكتر من تشغيل في نفس الوقت، وأي دمج نصّي
ممكن يسيب علامات تعارض جوه الملف ⇒ الملف يبقى JSON تالف وكل حاجة تعتمد عليه تفشل.

القاعدة الحاكمة: **مفيش فيديو يتمسح** — بنستخرج كل الأجزاء السليمة من الملف التالف،
ونعمل اتحاد مع نسختنا المحلية، ونكتب الملف من جديد سليم.

    python3 tools/repair_state.py            # يصلّح لو محتاج (ويقول عمل إيه)
    python3 tools/repair_state.py --check    # فحص بس (كود خروج 1 لو فيه تلف)
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = pathlib.Path(__import__("os").environ.get("DOLLARS_STATE") or (ROOT / "state"))

# الملفات وقائمة المفاتيح اللي تعرّف «عنصر حقيقي» جواها (عشان الاتحاد)
KNOWN = {"published.json": (["videos"], "video_id"),
         "queue.json": (["items"], "title"),
         "queue_skipped.json": (["items"], "title"),
         "produced.json": (["done"], None),
         "variety.json": (["seen"], None),
         "unlimited.json": (["used"], None)}


def salvage_objects(raw: str) -> list[dict]:
    """يستخرج كل كائن JSON سليم من نص ممكن يكون فيه تعارض دمج/تكرار."""
    dec = json.JSONDecoder()
    out: list[dict] = []
    i = 0
    while True:
        j = raw.find("{", i)
        if j < 0:
            break
        try:
            obj, end = dec.raw_decode(raw, j)
            if isinstance(obj, dict):
                out.append(obj)
            i = max(end, j + 1)
        except Exception:
            i = j + 1
    return out


def strip_markers(raw: str) -> str:
    """يشيل **سطور العلامات بس** ويسيب محتوى الطرفين.

    ده مقصود: عايزين نغطّف كل الفيديوهات المسجلة من الناحيتين (اتحاد بلا فقدان)،
    وبعدين الفحص بالكائنات السليمة هو اللي يفلتر التكرار.
    """
    keep = [ln for ln in raw.splitlines()
            if not (ln.startswith("<<<<<<<") or ln.startswith("=======") or ln.startswith(">>>>>>>"))]
    return "\n".join(keep)


def _key_of(obj: dict, key: str | None) -> str | None:
    if key and obj.get(key):
        return str(obj[key])
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)[:200]   # مفاتيح بديلة: المحتوى نفسه


def salvage_to_dict(raw: str, name: str) -> dict:
    """يحوّل نص تالف لقاموس بمفاتيح الملف المعروفة (يستخدمه موحّد الحالة كذلك)."""
    lists, idkey = KNOWN.get(name, (["videos"], "video_id"))
    items: dict[str, dict] = {}
    for obj in salvage_objects(strip_markers(raw)):
        if idkey and obj.get(idkey):
            items.setdefault(_key_of(obj, idkey), obj)
        for lst in lists:
            for it in (obj.get(lst) or []):
                if isinstance(it, dict):
                    items.setdefault(_key_of(it, idkey), it)
    return {lst: list(items.values()) for lst in lists}


def repair_file(path: pathlib.Path, check_only: bool = False) -> dict:
    name = path.name
    if name not in KNOWN:
        return {"file": name, "ok": True, "skipped": True}
    lists, idkey = KNOWN[name]
    raw = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    problems = []
    data = None
    if raw.strip():
        try:
            data = json.loads(raw)
        except Exception as e:
            problems.append(f"JSON تالف ({type(e).__name__})")
    if "<<<<<<<" in raw:
        problems.append("علامات تعارض دمج")
    if not problems:
        return {"file": name, "ok": True, "skipped": True}
    if check_only:
        return {"file": name, "ok": False, "problems": problems}
    # ── الإصلاح: نجمع كل العناصر السليمة (اتحاد) ──
    items: dict[str, dict] = {}
    for obj in salvage_objects(strip_markers(raw)):
        if idkey and obj.get(idkey):                 # عنصر منفرد (مش جوه المفتاح) — من التلف
            k = _key_of(obj, idkey)
            items.setdefault(k, obj)
        for lst in lists:
            for it in (obj.get(lst) or []):
                if isinstance(it, dict):
                    k = _key_of(it, idkey)
                    if k and (k not in items or len(json.dumps(it)) > len(json.dumps(items[k]))):
                        items[k] = it
    for lst in lists:
        for it in ((data or {}).get(lst) or []):
            if isinstance(it, dict):
                k = _key_of(it, idkey)
                items.setdefault(k, it)
    payload = {lst: list(items.values()) for lst in lists}
    if not payload[lists[0]] and data:
        payload = data                    # مفيش عناصر اتسجلت؟ ما نضيّعش أي حاجة
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"file": name, "ok": True, "fixed": True, "items": len(payload[lists[0]]),
            "problems": problems}


def main() -> int:
    check_only = "--check" in sys.argv
    rows = [repair_file(p, check_only=check_only) for p in sorted(STATE.glob("*.json"))]
    bad = [r for r in rows if not r.get("ok")]
    fixed = [r for r in rows if r.get("fixed")]
    for r in fixed:
        print(f"🛠️ {r['file']}: اتصلّح ({', '.join(r['problems'])}) · العناصر: {r['items']}")
    for r in bad:
        print(f"❌ {r['file']}: {', '.join(r['problems'])}")
    if check_only and bad:
        return 1
    if not fixed and not bad:
        print("✅ حالة المصنع سليمة (مفيش تلف)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
