#!/usr/bin/env python3
"""
🔎 محرّك الطلب — Dollars Studio
==============================
العنوان مش بيتألف من دماغنا: بيتاخد من **اللي الناس بتكتبه فعلًا في بحث يوتيوب**.

بنستخدم أوتوكومبليت بحث يوتيوب (بلا مفتاح ولا فلوس):

    https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q=<بذرة>

والنتيجة بتتخزن يوميًا في state/demand.json (كاش) عشان مانضربش السيرفر بلا داعي:

    from engine import demand
    demand.phrases("kinetic sand")      # ['kinetic sand asmr', 'kinetic sand cutting', …]
    demand.best_title_seed("satisfying") # أحسن عبارة عليها طلب حقيقي للنوع ده
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
def _state_path(rel: str = "") -> pathlib.Path:
    """مسار الحالة (احترام DOLLARS_STATE — الاختبارات تشتغل في مجلد مؤقت)."""
    import os as _os
    base = (_os.environ.get("DOLLARS_STATE") or "").strip()
    root = pathlib.Path(base) if base else (ROOT / "state")
    return (root / rel) if rel else root


CACHE = _state_path("demand.json")
SUGGEST = "https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&hl={hl}&q={q}"

# بذور كل نوع (اللي بنسأل بيها يوتيوب: «الناس بتدوّر على إيه؟»)
SEEDS = {
    "satisfying": ["kinetic sand", "oddly satisfying", "satisfying video", "sand cutting"],
    "sleep_ambience": ["rain sounds for sleeping", "sleep sounds", "black screen rain"],
    "focus_study": ["study with me", "brown noise", "focus music"],
    "story": ["wordless story", "silent cartoon", "bedtime story animation"],
    "facts": ["amazing facts", "did you know", "facts shorts"],
    "space_nature": ["nasa footage", "space facts", "galaxy zoom"],
    "pets_funny": ["funny cats", "cute dogs", "pets shorts"],
    "food_asmr": ["food asmr", "asmr eating", "crunchy asmr"],
    "water_nature": ["waterfall sounds", "ocean waves", "river nature"],
    "city_vibes": ["city night walk", "rainy city", "city ambience"],
    "space_cosmos": ["universe zoom", "space documentary shorts", "nebula"],
    "slow_macro": ["macro nature", "slow motion nature", "flowers macro"],
    "sky_timelapse": ["timelapse clouds", "sunset timelapse", "stargazing timelapse"],
    "machines_odd": ["oddly satisfying machines", "hydraulic press", "how it works machines"],
    "ocean_deep": ["deep sea creatures", "underwater footage", "ocean documentary"],
    "birds_wild": ["birds singing", "bird watching", "wild birds"],
    "lights_bokeh": ["bokeh lights", "abstract lights", "relaxing visuals"],
    "vintage_archive": ["old footage restored", "history archive footage", "vintage film"],
    "rain_nature": ["rain on window", "heavy rain", "thunderstorm sounds"],
    "asmr": ["asmr no talking", "tingles asmr", "asmr sounds"],
    "comfort_relax": ["cozy ambience", "relaxing video", "calm music"],
    "funny": ["funny shorts", "memes", "funny moments"],
    "fun_memes": ["funny animals", "instant regret", "fails"],
    "calm_wellness": ["meditation sounds", "anxiety relief", "breathing exercise"],
}
_TTL = 24 * 3600          # الكاش يوم كامل


def _load() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict) -> None:
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(d, ensure_ascii=False, indent=1)[:400_000], encoding="utf-8")
    except Exception:
        pass


def _get(q: str, hl: str = "en", timeout: int = 15) -> list[str]:
    url = SUGGEST.format(hl=hl, q=urllib.parse.quote(q))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Dollars/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    out: list[str] = []
    for m in re.finditer(r'"([^"\\]{3,80})"', raw):
        t = m.group(1).strip()
        if t and not t.startswith(("window.google", "yt", "ds", "hl", "client")) and t not in out:
            out.append(t)
    return out[:12]


def phrases(seed: str, hl: str = "en", force: bool = False) -> list[str]:
    """العبارات اللي الناس بتكمّلها بعد البذرة (طلب حقيقي، بلا مفتاح)."""
    key = f"{hl}:{seed.lower()}"
    cache = _load()
    ent = cache.get(key) or {}
    if not force and ent.get("phrases") and (time.time() - float(ent.get("at") or 0)) < _TTL:
        return list(ent["phrases"])
    try:
        got = _get(seed, hl=hl)
    except Exception:
        return list(ent.get("phrases") or [])          # الشبكة وقعت ⇒ الكاش أحسن من مفيش
    if got:
        cache[key] = {"at": time.time(), "phrases": got}
        _save(cache)
        return got
    return list(ent.get("phrases") or [])


def top_by_genre(gid: str, hl: str = "en", limit: int = 24) -> list[str]:
    """أعلى العبارات طلبًا لنوع معيّن (من كل بذوره)."""
    seeds = SEEDS.get(gid) or [gid.replace("_", " ")]
    out: list[str] = []
    for s in seeds:
        for p in phrases(s, hl=hl):
            p2 = p.lower().strip()
            if p2 and p2 not in out:
                out.append(p2)
            if len(out) >= limit:
                return out
    return out


CLEAN = re.compile(r"[^\w\s#&+'\-]")


def title_from_phrase(phrase: str, template: str | None = None) -> str:
    """يحوّل عبارة بحث لعنوان شهيّ: أول حرف كابيتال + قالب النوع لو موجود."""
    p = CLEAN.sub("", (phrase or "").strip())
    if not p:
        return ""
    p = p[0].upper() + p[1:]
    return (template or "{kw}").replace("{kw}", p) if template else p


def pick(genre: str, rnd=None, hl: str = "en", used=None) -> str | None:
    """يختار عبارة عليها طلب فعلًا ومش مستخدمة قبل كده (نفس فكرة «مش هنكررو»)."""
    pool = [p for p in top_by_genre(genre, hl=hl) if len(p) >= 6]
    if not pool:
        return None
    used_n = {re.sub(r"\W+", " ", (u or "").lower()).strip() for u in (used or [])}
    free = [p for p in pool if re.sub(r"\W+", " ", p).strip() not in used_n]
    pool = free or pool
    r = rnd or __import__("random")
    return r.choice(pool) if hasattr(r, "choice") else pool[0]


if __name__ == "__main__":      # عرض سريع: الناس بتدوّر على إيه؟
    import sys as _s
    gid = _s.argv[1] if len(_s.argv) > 1 else "satisfying"
    print(f"🔎 طلب حقيقي للنوع «{gid}»:")
    for i, ph in enumerate(top_by_genre(gid, limit=18), 1):
        print(f"  {i:>2}. {ph}")
