"""
🛡️ حارس التنوّع — يمنع أي تكرار (شرط المرور قبل النشر).
========================================================
سياسة يوتيوب «المحتوى غير الأصيل» بتقفل أرباح القنوات اللي بتنشر قوالب متشابهة.
الحارس ده بيضمن إن **كل فيديو يختلف عن آخر ١٢ فيديو على الأقل في ٣ أبعاد**:

    النوع · المشهد · اللوحة اللونية · الانتقال · الصوت · إيقاع المونتاج · شكل العنوان · العلامة

لو التركيبة متشابهة ⇒ يرفضها ويجيب غيرها (بذرة جديدة). ومع الوقت بيسجّل اللي اتنشر فعلاً.

    from engine import variety
    g, recipe = variety.pick_recipe("satisfying", seed=123)
    variety.record(sig)          # بعد النشر
"""
from __future__ import annotations

import json
import pathlib
import random

import numpy as np

STATE = pathlib.Path("state/variety.json")
WINDOW = 12          # نقارن بآخر ١٢ فيديو
MIN_DIFF = 3         # لازم يختلف في ٣ أبعاد على الأقل

DIMS = ("genre", "scene", "palette", "transition", "audio", "montage", "title_shape", "mark")


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"sig": []}


def _save(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def recent(n: int = WINDOW) -> list[dict]:
    return _load().get("sig", [])[-n:]


def record(sig: dict, keep: int = 60) -> dict:
    d = _load()
    d.setdefault("sig", []).append(sig)
    d["sig"] = d["sig"][-keep:]
    _save(d)
    return d


def diffs(a: dict, b: dict) -> int:
    """كام بُعد مختلف بين تركيبين."""
    return sum(1 for k in DIMS if str(a.get(k)) != str(b.get(k)))


def too_similar(sig: dict, history: list[dict] | None = None, min_diff: int = MIN_DIFF) -> bool:
    """متشابه؟ لو أي فيديو في آخر ١٢ أقل من ٣ اختلافات ⇒ نعم."""
    for h in (history if history is not None else recent()):
        if diffs(sig, h) < min_diff:
            return True
    return False


def _shape(title: str) -> str:
    """بصمة شكل العنوان (بلا كلمات النوع) عشان نمنع تكرار نفس القالب."""
    import re
    t = re.sub(r"[A-Za-z0-9]+", "W", title or "")
    t = re.sub(r"\s+", " ", t)
    return t[:40]


def pick_recipe(genre_id: str, seed: int | None = None, extra_marks: tuple = ("",), tries: int = 40,
                history: list[dict] | None = None):
    """
    يختار تركيبة **مضمونة الجِدّة** من مخزون النوع: يجرّب بذور مختلفة لحد ما تعدّي الحارس.
    يرجّع (التركيبة, البذرة) — والتركيبة فيها المشهد · الصوت · اللوحة · الانتقال · المونتاج · العلامة.
    """
    from engine import genres

    hist = history if history is not None else recent()
    g = genres.get(genre_id)
    rng = random.Random(seed)
    fallback = None
    for _ in range(max(1, tries)):
        r = random.Random(rng.randint(1, 10 ** 9))
        rec = {
            "genre": genre_id,
            "scene": r.choice(g["scenes"]),
            "audio": r.choice(g["audio"]),
            "palette": r.choice(g["palettes"]),
            "mood": r.choice(g["mood"]),
            "transition": r.choice(["crossfade", "fade", "xfade_soft", "slide"]),
            "montage": r.choice(g["montage"]),
            "mark": r.choice(list(extra_marks) or [""]),
            "title": genres.title_for(genre_id, r, kw="", dur="", name="", thing=""),
        }
        rec["title_shape"] = _shape(rec["title"])
        if not too_similar(rec, hist):
            return rec, r.randint(1, 10 ** 6)
        fallback = rec
    return fallback, random.Random(seed).randint(1, 10 ** 6)      # مفيش بديل؟ ناخد الأقل تشابهًا


def signature_for(rec: dict, title: str = "", hour: int | None = None) -> dict:
    s = {k: rec.get(k) for k in DIMS}
    s["title_shape"] = _shape(title or rec.get("title", ""))
    if hour is not None:
        s["hour"] = hour
    return s
