#!/usr/bin/env python3
"""
♾️ المخزون اللانهائي — «المكتبة لا محدودة» بشكل حقيقي، مش شعار.

الفكرة: عندنا **قاعدة** (ملفات مولّدة: 90 مؤثر · 12 موسيقى · 47 ملصق · 20 مشهد · 10 قصص · 6 قوالب ميمز)
فوقها **مساحة توليفات** رياضية: كل فيديو بياخد تركيبة مختلفة من
(مشاهد × مظهر × حركة كاميرا × موسيقى × لوحة ألوان × طبقات إضافات) — يعني ملايين النسخ
من غير ما نكرر، وكل نسخة **بتتولّد فعلًا وقت الطلب** (مش ملف متخزّن).

- `space_size()`   → حجم المساحة الحقيقي (رقم بالحساب).
- `combo(i)`       → التركيبة رقم i (نتيجة ثابتة لنفس الرقم).
- `next_combo()`   → التركيبة اللي بعدها من غير تكرار (العدّاد محفوظ في `state/unlimited.json`).
- `enrich(kw)`     → بتكمّل أي خانة ناقصة في وصفة الفيديو + تسجّل رقم التركيبة.
- `--stats` · `--next N` من سطر الأوامر.

كل التركيبات مبنية على **مشاهد وأصوات من عندنا** ⇒ صفر حقوق، صفر تكرار ممل.
"""
from __future__ import annotations

import itertools
import json
import math
import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import editor, fx, music, visuals  # noqa: E402

STATE = ROOT / "state" / "unlimited.json"

# ── لوحات الألوان: كل مجموعة مبنيّة على «مرجع بصري» (Pinterest/Openverse) بنحلّلها بكسل ──
PALETTES = {
    "night_blue":   ["#0b1a2a", "#1d3b53", "#7fa6c4"],
    "deep_space":   ["#080d1a", "#1b2a4a", "#c8b98a"],
    "ember":        ["#1a0f08", "#7a3b16", "#ffb457"],
    "forest_mist":  ["#0c1512", "#2f4f3a", "#a9d5b8"],
    "desert_dusk":  ["#241a12", "#8a5a35", "#f0c987"],
    "snow_light":   ["#eaf2f7", "#9fc0d6", "#33475e"],
    "paper_white":  ["#f2f2f2", "#8fd3ff", "#ffd166"],
    "zen_green":    ["#e9e4d6", "#8fb9a8", "#3d5a4c"],
    "rose_dawn":    ["#2a1620", "#a8557a", "#ffd9e6"],
    "amber_night":  ["#140f08", "#6b4a1c", "#ffcf70"],
    "ocean_deep":   ["#04121c", "#0e3b4d", "#6fd3d3"],
    "city_neon":    ["#0a0a12", "#3a1f5c", "#ff5fa2"],
    "lavender_dusk": ["#191428", "#5a4a8a", "#d9c9ff"],
    "moss_stone":   ["#12140f", "#4a5136", "#c7cf9a"],
    "copper_warm":  ["#1b1008", "#8c4a24", "#ffc98b"],
}

# ── مستويات الألوان (قوة التطبيق) والانتقالات — بتغيّر إحساس الفيديو نفسه ──
TINTS = [0.28, 0.34, 0.42, 0.50, 0.58]
TRANSITIONS = ["crossfade", "fade"]


def _scene_pool(pillar: str) -> list[str]:
    if pillar in ("sleep", "ambience"):
        pool = list(getattr(visuals, "SLEEP_SCENES", []) or [])
    elif pillar == "story":
        pool = list(getattr(visuals, "SMILE_SCENES", []) or [])
    else:
        pool = [s for s in visuals.SCENES if not s.startswith("stinger")]
    pool = [s for s in pool if s in visuals.SCENES]
    return sorted(dict.fromkeys(pool)) or sorted(visuals.SCENES)


def dimensions(pillar: str = "satisfying") -> dict:
    """أبعاد المساحة — كلها من حاجات موجودة عندنا فعلًا."""
    scenes = _scene_pool(pillar)
    return {
        "scenes": scenes,                                   # المشاهد المتاحة للعمود
        "looks": sorted(visuals.LOOKS),                     # مظاهر التدرّج اللوني
        "moves": sorted(editor.MOVES),                      # حركات الكاميرا الحقيقية
        "music": sorted(music.STYLES()),                    # أنماط موسيقانا
        "palettes": sorted(PALETTES),                        # لوحات المرجع البصري
        "tints": TINTS,                                     # قوة تطبيق اللوحة
        "transitions": TRANSITIONS,                         # نوع الانتقال
        "counts": {"scene_sets": 3, "fx_sets": len(fx.KINDS) if hasattr(fx, "KINDS") else 6},
    }


def space_size(pillar: str = "satisfying") -> int:
    """حجم المساحة = كل التركيبات الممكنة (رقم حقيقي بالحساب)."""
    d = dimensions(pillar)
    n = (len(d["scenes"]) * len(d["looks"]) * len(d["moves"]) * len(d["music"])
         * len(d["palettes"]) * len(d["tints"]) * len(d["transitions"]) * d["counts"]["scene_sets"]
         * d["counts"]["fx_sets"])
    # كل تركيبة بتاخد «مزاج» مشهد (مجموعة مقاطع) من 3 أشكال مختلفة
    return int(n)


def _stride(size: int) -> int:
    """خطوة كبيرة أوليّة مع size — تخلي الفيديوهات المتتالية مختلفة في كل حاجة (توزيع ذهبي)."""
    st = max(1, int(size * 0.618033988749895))
    while math.gcd(st, size) != 1:
        st += 1
    return st


def slot(index: int, pillar: str = "satisfying") -> int:
    """مكان التركيبة جوه المساحة — تبديل ذهبي: كل نداء بيبعد خطوة كبيرة (بلا تكرار لحد 77 مليون)."""
    size = space_size(pillar)
    return (_stride(size) * (int(index) % size)) % size


def combo(index: int, pillar: str = "satisfying") -> dict:
    """التركيبة رقم index — ثابتة دايمًا (نفس الرقم = نفس التركيبة)."""
    d = dimensions(pillar)
    dims = [d["scenes"], d["looks"], d["moves"], d["music"], d["palettes"], d["tints"],
            d["transitions"], list(range(d["counts"]["scene_sets"])), list(range(d["counts"]["fx_sets"]))]
    idx = slot(index, pillar)
    pick = []
    for axis in dims:
        pick.append(axis[idx % len(axis)])
        idx //= len(axis)
    scene, look, move, style, pal, tint, trans, scene_set, fx_set = pick
    rng = random.Random(1000 + int(combo.__name__ and 0) + int(index))
    n_scenes = 3 + scene_set                      # 3 · 4 · 5 مشاهد لكل فيديو
    pool = [scene] + [s for s in d["scenes"] if s != scene]
    rng.shuffle(pool)
    return {
        "combo_id": int(index) % space_size(pillar),
        "scenes": pool[:n_scenes],
        "look": look,
        "moves": [move] + [m for m in d["moves"] if m != move][:2],
        "music": style,
        "palette": PALETTES[pal],
        "palette_name": pal,
        "palette_strength": tint,
        "transition": trans,
        "fx_set": fx_set,
    }


# ───────────────────────── العدّاد (من غير تكرار) ─────────────────────────

def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"index": 0, "used": [], "by_pillar": {}}


def _save(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    st["used"] = st.get("used", [])[-4000:]          # نحفظ آخر 4000 رقم كفاية لمنع التكرار
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def next_combo(pillar: str = "satisfying", advance: bool = True) -> dict:
    """التركيبة اللي بعدها — من غير تكرار آخر آلاف الفيديوهات."""
    st = _load()
    size = space_size(pillar)
    used = set(int(x) for x in st.get("used", []))
    i = int(st.get("index", 0)) % size
    for _ in range(size):
        if i not in used:
            break
        i = (i + 1) % size
    out = combo(i, pillar)
    if advance:
        st["index"] = (i + 1) % size
        st.setdefault("used", []).append(i)
        st.setdefault("by_pillar", {})[pillar] = st.get("by_pillar", {}).get(pillar, 0) + 1
        _save(st)
    return out


# الموسيقى المسموحة لكل عمود (عشان التنويع ما يبوظش المزاج)
PILLAR_MUSIC = {
    "satisfying": ["dream_pulse", "lofi_keys", "glass_garden", "kalimba_dusk", "warm_pad"],
    "sleep": ["night_drone", "warm_pad", "ocean_lullaby", "harp_mist", "cosmic_pad"],
    "ambience": ["night_drone", "warm_pad", "ocean_lullaby", "harp_mist", "cosmic_pad"],
    "focus": ["lofi_keys", "warm_pad", "glass_garden", "kalimba_dusk", "city_night"],
    "story": ["music_box", "lullaby_bell", "harp_mist", "kalimba_dusk"],
}


def enrich(kw: dict, pillar: str = "satisfying", advance: bool = True) -> dict:
    """بتكمّل أي خانة ناقصة في وصفة الفيديو بتركيبة جديدة من المساحة + تسجّل رقمها."""
    c = next_combo(pillar, advance=advance)
    kw = dict(kw)
    # 1) نكمّل أي خانة فاضية من التركيبة
    for key in ("scenes", "look", "moves", "music"):
        if not kw.get(key):
            kw[key] = c[key]
    # 2) تنويع حقيقي كل فيديو: حركة الكاميرا · الانتقال · قوة اللوحة
    kw["moves"] = c["moves"]
    kw["transition"] = c["transition"]
    kw["palette_strength"] = c["palette_strength"]
    # 3) مشهد إضافي طازة من المساحة (مع الحفاظ على هوية العمود) + سقف 6 مشاهد
    scenes = list(kw.get("scenes") or [])
    for extra in c["scenes"]:
        if len(scenes) >= 6:
            break
        if extra not in scenes:
            scenes.append(extra)
    if scenes:
        kw["scenes"] = scenes
    # 4) الموسيقى: تدور جوه الأنماط المناسبة للعمود (الوصفة بتحدد المزاج، والمساحة بتحدد النمط)
    pool = [m for m in PILLAR_MUSIC.get(pillar, PILLAR_MUSIC["satisfying"]) if m in music.STYLES()]
    if pool:
        kw["music"] = pool[c["combo_id"] % len(pool)]
    kw["unlimited"] = {"combo_id": c["combo_id"], "palette_name": c["palette_name"],
                       "fx_set": c["fx_set"], "space_size": space_size(pillar)}
    return kw


def stats() -> dict:
    st = _load()
    out = {}
    for pillar in ("satisfying", "sleep", "focus", "story"):
        out[pillar] = {"space": space_size(pillar), "made": st.get("by_pillar", {}).get(pillar, 0)}
    out["used_total"] = len(st.get("used", []))
    out["base_stock"] = {"sfx": len(getattr(__import__("engine.sfx", fromlist=["SFX"]), "SFX", {})),
                         "music": len(music.STYLES()), "scenes": len(visuals.SCENES),
                         "looks": len(visuals.LOOKS)}
    return out


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "--stats":
        s = stats()
        print("♾️ مساحة المخزون اللانهائي")
        for k, v in s.items():
            if isinstance(v, dict) and "space" in v:
                print(f"  • {k:11s} تركيبات: {v['space']:,} · اتعمل منها: {v['made']}")
            elif isinstance(v, dict):
                print(f"  • {k}: {v}")
            else:
                print(f"  • {k}: {v}")
        return 0
    if args[0] == "--next":
        n = int(args[1]) if len(args) > 1 else 3
        pillar = args[2] if len(args) > 2 else "satisfying"
        for i in range(n):
            c = next_combo(pillar)
            print(f"#{c['combo_id']:>6} · {len(c['scenes'])} مشاهد [{', '.join(c['scenes'][:3])}] · "
                  f"{c['look']} · {c['music']} · {c['palette_name']} · {c['transition']}")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
