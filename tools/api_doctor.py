#!/usr/bin/env python3
"""
🩺 دكتور الـAPIs — بيجرّب كل مساعد **بنداء حقيقي** ويقول الحقيقة: شغال / ناقص مفتاح / وقع.
=========================================================================================
مفيش أي تجميل: كل سطر فيه نتيجة نداء فعلي على الخدمة نفسها.

    python tools/api_doctor.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import providers  # noqa: E402


def check(name: str, fn) -> tuple[str, str]:
    t0 = time.time()
    try:
        out = fn()
    except Exception as e:
        return "❌", f"وقع: {type(e).__name__}: {str(e)[:90]}"
    ms = int((time.time() - t0) * 1000)
    if isinstance(out, list):
        if out:
            first = out[0]
            sample = (first.get("title") or first.get("name") or first.get("tags")
                      or first.get("url") or "")
            return "✅", f"{len(out)} نتيجة · {str(sample)[:58]} ({ms}ms)"
        return "⚪", "مفيش نتايج (مفتاح ناقص أو مفيش تطابق)"
    if isinstance(out, dict):
        if out:
            return "✅", f"{json.dumps(out, ensure_ascii=False)[:70]} ({ms}ms)"
        return "⚪", "فاضي (مفتاح ناقص)"
    if isinstance(out, str):
        if out.strip():
            return "✅", f"{out.strip()[:70]} ({ms}ms)"
        return "⚪", "مفيش رد (مفتاح ناقص أو الخدمة رفضت)"
    return "⚪", "مفيش رد"


CHECKS = [
    ("Pixabay صور", lambda: providers.pixabay_images("rain window", per=3)),
    ("Pixabay فيديو", lambda: providers.pixabay_videos("rain", per=2)),
    ("Pexels صور", lambda: providers.pexels_images("night sky", per=3)),
    ("Pexels فيديو", lambda: providers.pexels_videos("water", per=2)),
    ("Openverse (بلا مفتاح)", lambda: providers.openverse_images("storm", per=3)),
    ("Wikimedia (بلا مفتاح)", lambda: providers.wikimedia_images("cumulus cloud", per=3)),
    ("NASA (بلا مفتاح)", lambda: providers.nasa_images("nebula", per=3)),
    ("YouTube Suggest (بلا مفتاح)", lambda: providers.youtube_suggest("rain sounds for sleep")),
    ("REST Countries (بلا مفتاح)", lambda: providers.restcountries("Egypt")),
    ("GNews", lambda: providers.gnews("science", n=3)),
    ("Currents", lambda: providers.currents("space", n=3)),
    ("Groq (نص)", lambda: providers.groq("اكتب سطر واحد بس: عنوان شورت عن المطر", max_tokens=60)),
    ("Gemini (نص)", lambda: providers.gemini("اكتب سطر واحد بس: عنوان شورت عن المطر", max_tokens=60)),
    ("Freesound (CC0)", lambda: providers.freesound("rain", n=3)),
]


def main() -> int:
    ready = providers.available()
    print("🔑 المفاتيح الموجودة:", json.dumps({k: v for k, v in ready.items() if isinstance(v, bool)},
                                            ensure_ascii=False))
    print("\n🧪 نداءات حقيقية:\n" + "-" * 78)
    good = 0
    for name, fn in CHECKS:
        mark, msg = check(name, fn)
        good += mark == "✅"
        print(f"{mark} {name:28} | {msg}")
    print("-" * 78)
    print(f"\n💪 مساعدين شغالين فعلاً: {good}/{len(CHECKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
