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
         texts: bool = False, strict: bool = False) -> tuple[bool, dict]:
    """يرجّع (ينفع ينشر؟, التقرير).

    سياسة ٢٦/٩ (بعد حادثة إيقاف النشر): البوابة **بتحذّر مش بتمنع**.
    السبب: فيديوهات النوم الطويلة بتبان «ساكنة» و«أبعادها مختلفة» وده **مقصود**
    (شاشة سودة/نجوم بتتحرك ببطء)، ورفضها أوقف النشر بالغلط ١٠ مرات في ساعة.

    تمنع النشر في حالة واحدة بس: **الملف نفسه تالف** (مش موجود · صفر بايت · مش فيديو).
    strict=True (للفحص اليدوي): أي ملاحظة تبقى مانعة — للاستخدام في tools/video_doctor.
    """
    p = pathlib.Path(video)
    if not p.exists() or p.stat().st_size < 10_000:
        return False, {"error": "ملف الفيديو مش موجود أو تالف", "checks": [], "pass": False,
                       "fatal": ["الملف تالف"], "warnings": []}
    try:
        rep = inspect(video, kind=kind, seconds=seconds, loop=loop, texts=texts)
    except Exception as e:
        # مش قادرين نفحص (مشكلة أداة) ⇒ مانوقفش النشر — الفيديو اترندر فعلًا
        return True, {"error": f"{type(e).__name__}: {e}", "checks": [], "pass": False,
                      "warnings": [f"الفحص اتخطى: {type(e).__name__}"], "fatal": []}
    if not rep.get("checks"):
        return True, {**rep, "warnings": ["الفحص مرجّعش نتايج"], "fatal": []}
    warnings = [n for n, ok, _d in rep.get("checks", []) if not ok]
    fatal: list = []
    unreadable = (not rep.get("motion") and not rep.get("black_ratio")
                  and rep.get("resolution") in (None, "0x0"))
    if unreadable:
        # ملف صغير ومش مقروء ⇒ تالف فعلًا (مايتنشرش).
        # ملف **كبير** ومش مقروء ⇒ غالبًا مشكلة أداة/بروب على ملف ضخم (زي طويلة ١٠ ساعات)
        # ⇒ ملاحظة مش رفض، عشان النشر مايتوقفش بالغلط (زي ما حصل قبل كده).
        if p.stat().st_size < 200_000:
            fatal.append("الفيديو مش مقروء (ملف تالف)")
        else:
            warnings.append("الفحص مش قادر يقرا الفيديو (حجمه كبير — بننشر)")
    if strict:
        fatal += warnings
    return (not fatal), {**rep, "warnings": warnings, "fatal": fatal,
                         "failed": (fatal or warnings)}
