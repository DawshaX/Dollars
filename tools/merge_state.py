#!/usr/bin/env python3
"""🔀 توحيد ملفات الحالة بين نسختنا ونسخة الريموت (اتحاد حقيقي).

ليه؟ لأن أكتر من تشغيل (ساعة · يومي · تفريغ الطابور · تخطيط) بيكتبوا نفس ملفات الحالة في
نفس الوقت؛ فأي تعارض في `state/*.json` كان بيوقّف `git pull --rebase` والتشغيل بيفشل
(حصل فعلًا 27/09). هنا بنعمل **اتحاد** للقوائم والمفاتيح بدل ما نرمي أي تسجيل.

الاستخدام في أي workflow بعد الدمج/التعارض:
    python3 tools/merge_state.py            # مع origin/main
    python3 tools/merge_state.py origin/main
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
REMOTE = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
MARK = "<<<<<<<"


def _git_show(ref: str, path: str):
    try:
        r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout.decode("utf-8", "ignore"))
    except Exception:
        return None


def _stage(which: int, path: str):
    """نسخة مرحلة من التعارض: 2 = بتاعتنا · 3 = بتاعة الريموت"""
    try:
        r = subprocess.run(["git", "show", f":{which}:{path}"], cwd=ROOT, capture_output=True)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout.decode("utf-8", "ignore"))
    except Exception:
        return None


def union(a, b, depth: int = 0):
    """اتحاد: نسختنا ليها الأولوية، وبنضيف اللي عندهم من غير تكرار."""
    if depth > 8:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = union(out[k], v, depth + 1) if k in out else v
        return out
    if isinstance(a, list) and isinstance(b, list):
        seen, out = set(), []
        for it in list(a) + list(b):
            key = json.dumps(it, sort_keys=True, ensure_ascii=False, default=str)
            if key not in seen:
                seen.add(key)
                out.append(it)
        return out
    return a


def merge_file(p: pathlib.Path) -> bool:
    raw = p.read_text(encoding="utf-8", errors="ignore")
    rel = str(p.relative_to(ROOT))
    ours = theirs = None
    if MARK in raw:                              # ملف عليه علامات تعارض ⇒ ناخد النسختين المرحلتين
        ours, theirs = _stage(2, rel), _stage(3, rel)
        if ours is None or theirs is None:
            return False
    else:
        try:
            ours = json.loads(raw)
        except Exception:
            return False
        theirs = _git_show(REMOTE, rel)
        if theirs is None:
            return False
    merged = union(ours, theirs)
    new = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    if new != raw:
        p.write_text(new, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed = 0
    for p in sorted(STATE.glob("*.json")):
        try:
            if merge_file(p):
                changed += 1
        except Exception as e:
            print(f"⚠️ {p.name}: {type(e).__name__}")
    print(f"🔀 توحيد الحالة: {changed} ملف اتحدّث")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
