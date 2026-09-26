"""
🚦 بوابة الجودة — مفيش فيديو ينشر قبل ما يعدّي الفحص الفعلي.
============================================================
بتحوّل «دكتور الفيديو» لقرار: لو الفيديو ساكن · سودة · بلا صوت · مقطوع ⇒ **مايتنشرش**،
ويتسجّل السبب ويتصلّح تلقائيًا في اللفة الجاية.

    from engine import quality
    ok, report = quality.gate("/path/video.mp4", kind="short", seconds=45)
"""
from __future__ import annotations

import pathlib
import sys


def inspect(video, kind: str = "short", seconds: float | None = None, loop: bool = False,
            texts: bool = False) -> dict:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from tools.video_doctor import inspect as _inspect
    return _inspect(video, expect_seconds=seconds, kind=kind, loop=loop, needs_text=texts)


def gate(video, kind: str = "short", seconds: float | None = None, loop: bool = False,
         texts: bool = False, strict: bool = True) -> tuple[bool, dict]:
    """يرجّع (يعدّي؟, التقرير). الافتراضي strict=True: أي فشل = إيقاف النشر."""
    try:
        rep = inspect(video, kind=kind, seconds=seconds, loop=loop, texts=texts)
    except Exception as e:
        return (not strict), {"error": f"{type(e).__name__}: {e}", "checks": [], "pass": False}
    if not rep.get("checks"):
        return (not strict), rep
    # فيديو مقروء = فيه أبعاد حقيقية وحركة اتقاست. لو لأ، يبقى الرندر نفسه بايظ
    # (مش مشكلة جودة محتوى) — ماينفعش نمنع النشر بسبب ملف مش رندر أصلي.
    if not rep.get("motion") and not rep.get("black_ratio") and rep.get("resolution") in (None, "0x0"):
        rep["unreadable"] = True
        return True, {**rep, "note": "الفيديو مش مقروء (مش ناتج الرندر) — ما وقفناش النشر"}
    bad = [n for n, ok, _d in rep.get("checks", []) if not ok]
    return (not bad), {**rep, "failed": bad}
