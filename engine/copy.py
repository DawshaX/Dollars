"""
✍️ الكوبي الذكي — العناوين والوصف والهاشتاجات بلغات الدنيا (يوتيوب لكل الكون).
================================================================================
بيستخدم المساعدين الجدد:
- **YouTube Suggest**: الكلمات اللي الناس فعلاً بتدوّر بيها (طلب حقيقي مش تخمين).
- **Groq / Gemini (LLM)**: عنوان بيفتح النفس في ثانية · وصف مفيد · ترجمات لعدة لغات.

وكل ده **مكاش** في `state/copy_cache.json` (مفيش نداء مكرر لنفس الموضوع).
لو مفيش مفاتيح أو الخدمة واقعة: بيرجع {} بهدوء والمصنع يكمّل ببياناته العادية.

    from engine import copy
    extra = copy.enrich({"pillar": "sleep", "kw": "Rain Sounds", "kind": "short", "seconds": 60})
    # → {"titles": [...], "hook": "...", "tags": [...], "localizations": {"es": {...}, ...}}
"""
from __future__ import annotations

import json
import pathlib
import re

from engine import providers

CACHE = pathlib.Path("state/copy_cache.json")

# لغات الدبلجة/التدويل — الأسواق الكبيرة على يوتيوب
LANGS = {
    "ar": "العربية", "es": "Español", "pt": "Português", "hi": "हिन्दी",
    "id": "Bahasa Indonesia", "fr": "Français", "de": "Deutsch", "ru": "Русский",
    "ja": "日本語", "tr": "Türkçe", "ko": "한국어", "vi": "Tiếng Việt",
}

BANNED = ("كذب", "fake", "clickbait", "شات", "scam", "guarantee", "100% cure")


def _load() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(spec: dict) -> str:
    return f"{spec.get('pillar')}|{spec.get('kw')}|{spec.get('kind')}|{spec.get('seconds') or spec.get('hours')}"


def real_keywords(kw: str, limit: int = 12) -> list[str]:
    """كلمات بحث حقيقية من يوتيوب (Suggest) — الطلب الفعلي مش التخمين."""
    out: list[str] = []
    for q in (kw, f"{kw} for sleeping", f"{kw} 8 hours", f"{kw} black screen"):
        for s in providers.youtube_suggest(q):
            s = s.strip().lower()
            if s and s not in out and len(s) < 60:
                out.append(s)
        if len(out) >= limit:
            break
    return out[:limit]


def _prompt(spec: dict, kw_suggest: list[str], lang: str, lang_name: str) -> str:
    return (
        f"قناة يوتيوب بتعمل فيديوهات {spec.get('kind')} عن: {spec.get('kw')} "
        f"(نوع المحتوى: {spec.get('pillar')}، المدة: {spec.get('seconds') or spec.get('hours')}).\n"
        f"كلمات بحث حقيقية من يوتيوب: {', '.join(kw_suggest[:8])}\n\n"
        f"اكتب باللغة {lang_name} فقط، وبصيغة JSON بالشكل ده بالظبط:\n"
        '{"title": "عنوان أقل من 95 حرف، مغناطيسي وبصادق بدون مبالغة كاذبة", '
        '"description": "وصف مفيد من 3 جمل: إيه ده · لمين · إيه اللي مميز (بدون وعود كاذبة)", '
        '"tags": ["8-12 وسم من كلمات البحث الحقيقية"]}\n'
        "ممنوع: أي وعد كاذب أو كلام مش حقيقي أو وعود علاجية."
    )


def _parse(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
    except Exception:
        return {}
    out = {}
    if d.get("title"):
        out["title"] = str(d["title"]).strip()[:100]
    if d.get("description"):
        out["description"] = str(d["description"]).strip()[:4800]
    if isinstance(d.get("tags"), list):
        out["tags"] = [str(t).strip() for t in d["tags"] if str(t).strip()][:20]
    return out


def enrich(spec: dict, langs: tuple = ("ar", "es", "pt", "hi", "id"), use_llm: bool = True) -> dict:
    """بيثري بيانات الفيديو: عنوان أحسن + hook + وسوم حقيقية + ترجمات لعشرات اللغات."""
    ck = _key(spec)
    cache = _load()
    if cache.get(ck, {}).get("day") == providers._env("COPY_DAY") or cache.get(ck):
        return cache[ck] if not cache.get(ck, {}).get("_stale") else {}

    kw = spec.get("kw") or ""
    suggests = real_keywords(kw)
    out: dict = {"titles": [], "hook": "", "tags": [], "localizations": {}, "suggests": suggests}
    if not suggests:
        out["_stale"] = True

    if use_llm and providers.available().get("groq" if providers.keys()["groq"] else "gemini"):
        eng = _parse(providers.llm(_prompt(spec, suggests, "en", "English"),
                                   system="خبير كوبي يوتيوب صادق — ممنوع أي كلام كاذب.", json_mode=False))
        if eng.get("title"):
            out["titles"].append(eng["title"])
            out["hook"] = eng["title"][:60]
        if eng.get("description"):
            out["description"] = eng["description"]
        if eng.get("tags"):
            out["tags"] = eng["tags"]
        for code in langs:                                   # تدويل البيانات (يوتيوب يعرضها بلغة المشاهد)
            if code == "en":
                continue
            got = _parse(providers.llm(_prompt(spec, suggests, code, LANGS[code]),
                                       system=f"اكتب باللغة {LANGS[code]} فقط — كلام صادق مش مبالغ فيه."))
            if got.get("title"):
                out["localizations"][code] = {"title": got["title"][:100],
                                              "description": got.get("description", "")[:4800]}
    out["tags"] = [t for t in out["tags"] if not any(b in t.lower() for b in BANNED)]
    if out["titles"] or out["localizations"] or out["tags"]:
        cache[ck] = out
        _save(cache)
    return out
