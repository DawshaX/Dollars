"""
🔎 طبقة البحث والمراجع — Dollars Studio
========================================
بتخلّي المصنع **يبحث بنفسه** ويفهم السوق والمرجع البصري — من غير ما ياخد حاجة مسروقة:

1) **مرجع بصري (Pinterest وأمثاله)**: بيجمع روابط بحث Pinterest + صور مرجعية من مكتبات
   مفتوحة (Openverse / Pixabay / Pexels) في `docs/refs/` — **للمشاهدة والتحليل فقط**،
   ومحفوظ في `state/refs.json` بمصدره وترخيصه. ممنوع أي ملف من هنا يدخل فيديو.
2) **أرقام السوق**: بيسحب أكثر الفيديوهات مشاهدة في تخصصاتنا من يوتيوب نفسه
   ويحفظها في `state/trends.json` (طلب حقيقي) — والعقل يستخدمها في تعديل أوزانه.

    python engine/refs.py --board "rain on window night"      # لوحة مراجع بصرية
    python engine/refs.py --pinterest "kinetic sand satisfying" # مراجع Pinterest (روابط)
    python engine/refs.py --trends --apply                     # أرقام السوق + تغذية العقل
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
REFS = ROOT / "docs" / "refs"
sys.path.insert(0, str(ROOT))

UA = {"User-Agent": "Mozilla/5.0 (compatible; DollarsStudio/1.0; reference-only)"}

# تخصصاتنا (نستخدمها في بحث السوق)
NICHES = [
    "rain sounds for sleeping black screen",
    "10 hours sleep ambience",
    "kinetic sand satisfying",
    "wordless animated short film",
    "cozy fireplace ambience",
    "brown noise focus study",
]

PILLAR_KEYS = {
    "sleep": ("rain", "sleep", "night", "thunder", "black screen", "storm", "ocean", "snow", "fireplace",
              "ambience", "noise", "10 hours", "8 hours", "3 hours"),
    "satisfying": ("satisfying", "sand", "slime", "asmr", "oddly", "kinetic", "hydraulic", "pendulum",
                   "loop", "relaxing video"),
    "story": ("story", "animation", "cartoon", "animated short", "wordless", "kids", "short film"),
    "focus": ("focus", "study", "concentration", "brown noise", "pomodoro"),
}


def _get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _jload(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _jdump(p, obj):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ───────────────────────── 1) المراجع البصرية ─────────────────────────

def pinterest_links(query: str, n: int = 6) -> list:
    """روابط Pinterest للبحث البصري (مرجع بالعين — بلا أي سحب ملفات ولا كسر شروط)."""
    base = "https://www.pinterest.com/search/pins/?q=" + urllib.parse.quote(query)
    variants = [
        (query, base),
        (f"{query} aesthetic", base + "+aesthetic"),
        (f"{query} color palette", base + "+color+palette"),
        (f"{query} composition", base + "+composition"),
        (f"{query} moodboard", base + "+moodboard"),
        (f"{query} lighting", base + "+lighting"),
    ]
    return [{"label": lbl, "url": url} for lbl, url in variants[:n]]


def board(query: str, limit: int = 8, sources=("openverse", "pixabay", "pexels")) -> dict:
    """
    لوحة مراجع: صور صغيرة من مكتبات مفتوحة (بترخيص موثّق) + روابط Pinterest.
    ⚠️ كل اللي هنا **مرجع بصري للمشاهدة والتحليل** — ممنوع يتحط في أي فيديو.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:48] or "board"
    out_dir = REFS / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    items, errors = [], []

    # Openverse (بلا مفتاح)
    try:
        q = urllib.parse.urlencode({"q": query, "page_size": min(limit, 12), "license_type": "all"})
        d = json.loads(_get(f"https://api.openverse.org/v1/images/?{q}").decode("utf-8"))
        for it in d.get("results", [])[:limit]:
            items.append({"source": "openverse", "title": (it.get("title") or "")[:80],
                          "creator": it.get("creator"), "license": it.get("license"),
                          "url": it.get("foreign_landing_url") or it.get("url"),
                          "thumb": it.get("thumbnail") or it.get("url")})
    except Exception as e:
        errors.append(f"openverse: {type(e).__name__}")

    # ويكيميديا كومنز (بلا مفتاح)
    if "wikimedia" in sources:
        items += wikimedia_refs(query, limit=max(2, limit // 2))

    # Pixabay / Pexels (بالمفاتيح — بأي اسم متعارف عليه)
    pbay, pxls = _key("PIXABAY_API_KEY", "PIXABAY_KEY"), _key("PEXELS_API_KEY", "PEXELS")
    if pbay and "pixabay" in sources:
        try:
            q = urllib.parse.urlencode({"key": pbay, "q": query,
                                        "image_type": "photo", "per_page": limit})
            d = json.loads(_get(f"https://pixabay.com/api/?{q}").decode("utf-8"))
            for it in d.get("hits", [])[:limit]:
                items.append({"source": "pixabay", "title": (it.get("tags") or "")[:80], "creator": it.get("user"),
                              "license": "Pixabay", "url": it.get("pageURL"), "thumb": it.get("previewURL")})
        except Exception as e:
            errors.append(f"pixabay: {type(e).__name__}")
    if pxls and "pexels" in sources:
        try:
            req = urllib.request.Request(
                "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": query, "per_page": limit}),
                headers={**UA, "Authorization": pxls})
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.loads(r.read().decode("utf-8"))
            for it in d.get("photos", [])[:limit]:
                items.append({"source": "pexels", "title": (it.get("alt") or "")[:80],
                              "creator": it.get("photographer"), "license": "Pexels",
                              "url": it.get("url"), "thumb": (it.get("src") or {}).get("small")})
        except Exception as e:
            errors.append(f"pexels: {type(e).__name__}")

    saved = []
    for i, it in enumerate(items):
        if not it.get("thumb"):
            continue
        try:
            raw = _get(it["thumb"], timeout=20)
            ext = ".jpg" if not it["thumb"].lower().endswith(".png") else ".png"
            p = out_dir / f"{i+1:02d}_{it['source']}{ext}"
            p.write_bytes(raw)
            it["file"] = str(p.relative_to(ROOT))
            saved.append(it)
        except Exception as e:
            errors.append(f"thumb {i}: {type(e).__name__}")

    board_doc = {
        "query": query, "saved": len(saved), "sources_tried": list(sources), "errors": errors,
        "pinterest": pinterest_links(query),
        "rule": "مرجع بصري للمشاهدة والتحليل فقط — ممنوع أي ملف من هنا يدخل فيديو (قاعدة صفر سرقة).",
        "made": datetime.now(timezone.utc).isoformat(),
    }
    _jdump(REFS / f"{slug}.json", board_doc)
    old = _jload(STATE / "refs.json", {"boards": []}) or {"boards": []}
    old["boards"] = [b for b in old.get("boards", []) if b.get("query") != query] + [board_doc]
    _jdump(STATE / "refs.json", old)
    return board_doc



# ─────────────── 2) تحليل المرجع البصري ⇒ لوحة ألوان حقيقية ───────────────
# بنفتح صور المراجع (المحفوظة عندنا في docs/refs/<slug>/) ونحلّلها **بكسل حقيقي**:
# الألوان السايدة · السطوع · التباين · التشبّع · توزيع الفاتح/الغامق.
# الناتج: لوحة ألوان بتتطبّق فعلًا في تدرّج ألوان الفيديو (`grade.split_tone`) —
# ودي طريقة استخدام المرجع البصري: **إلهام وتحليل، مش نسخ ملفات**.

def _quant_colors(img, n: int = 6) -> list:
    """أهم الألوان في الصورة بنسبتها (تحليل بكسل حقيقي)."""
    small = img.convert("RGB").resize((160, 160))
    q = small.quantize(colors=n, method=2)
    pal = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    out = []
    total = sum(c for c, _ in counts) or 1
    for cnt, idx in counts:
        r, g, b = pal[idx * 3:idx * 3 + 3]
        out.append({"hex": f"#{r:02x}{g:02x}{b:02x}", "rgb": [r, g, b], "share": round(cnt / total, 3),
                    "lum": round((0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0, 3)})
    return out


def _img_stats(img) -> dict:
    import numpy as np
    a = np.asarray(img.convert("RGB").resize((160, 160)), dtype=np.float32) / 255.0
    lum = 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]
    mx, mn = a.max(axis=2), a.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    warm = float((a[:, :, 0] - a[:, :, 2]).mean())        # دافي + / بارد -
    return {"brightness": round(float(lum.mean()), 3), "contrast": round(float(lum.std()), 3),
            "saturation": round(float(sat.mean()), 3), "warmth": round(warm, 3),
            "dark_share": round(float((lum < 0.25).mean()), 3),
            "bright_share": round(float((lum > 0.75).mean()), 3)}


def analyze_refs(query: str, limit: int = 6) -> dict:
    """يحلّل صور لوحة مراجع موجودة (أو يجيبها) ويرجّع لوحة ألوان + إحصاءات."""
    from PIL import Image
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:48] or "board"
    doc = _jload(REFS / f"{slug}.json", {}) or {}
    if not doc.get("saved"):
        doc = board(query, limit=limit)
    files = sorted((REFS / slug).glob("*.jpg")) + sorted((REFS / slug).glob("*.png"))
    per, colors, stats = [], {}, []
    for f in files[:limit]:
        try:
            im = Image.open(f)
            c = _quant_colors(im, 6)
            st = _img_stats(im)
            for x in c:
                colors[x["hex"]] = colors.get(x["hex"], 0.0) + x["share"]
            stats.append(st)
            per.append({"file": f.name, "colors": c, "stats": st})
        except Exception as e:
            doc.setdefault("errors", []).append(f"تحليل {f.name}: {type(e).__name__}")
    top = [k for k, _ in sorted(colors.items(), key=lambda kv: -kv[1])[:6]]
    agg = {k: round(sum(s[k] for s in stats) / max(1, len(stats)), 3) for k in
           ("brightness", "contrast", "saturation", "warmth", "dark_share", "bright_share")} if stats else {}
    # إضاءة ومزاج مستنتجين من الأرقام الحقيقية
    mood = []
    if agg.get("brightness", 0) < 0.30:
        mood.append("ليل / غامق")
    if agg.get("brightness", 0) > 0.62:
        mood.append("نهار / فاتح")
    if agg.get("warmth", 0) > 0.03:
        mood.append("دافي")
    if agg.get("warmth", 0) < -0.03:
        mood.append("بارد")
    if agg.get("contrast", 0) > 0.20:
        mood.append("تباين عالي")
    if agg.get("saturation", 0) > 0.35:
        mood.append("مشبع بالألوان")
    elif agg.get("saturation", 0) < 0.16:
        mood.append("هادئ الألوان")
    out = {"query": query, "images": len(per), "palette": top, "stats": agg, "mood": mood,
           "per_image": per, "rule": "تحليل بكسل فقط — مفيش ملف مرجعي بيدخل أي فيديو",
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    old = _jload(STATE / "refs.json", {}) or {}
    old.setdefault("palettes", {})[slug] = out
    old["palettes"][slug]["query"] = query
    _jdump(STATE / "refs.json", old)
    board_doc = _jload(REFS / f"{slug}.json", {}) or {}
    board_doc["palette"] = {"colors": top, "stats": agg, "mood": mood}
    _jdump(REFS / f"{slug}.json", board_doc)
    return out


def palette_for(topic: str, live: bool = True) -> dict:
    """لوحة الألوان المرجعية لتخصص: من التحليل الحقيقي لو موجود، وإلا من وصفة المرجع عندنا."""
    slug = re.sub(r"[^a-z0-9]+", "-", (topic or "").lower()).strip("-")[:48] or "board"
    doc = _jload(STATE / "refs.json", {}) or {}
    hit = (doc.get("palettes") or {}).get(slug)
    if hit and hit.get("palette"):
        return {"source": "analyzed", "colors": hit["palette"], "stats": hit.get("stats", {}),
                "mood": hit.get("mood", []), "images": hit.get("images", 0)}
    rec = RECIPES.get((topic or "").lower())
    if rec:
        return {"source": "recipe", "colors": rec.get("palette", []), "stats": {}, "mood": [rec.get("mood", "")]}
    return {"source": "none", "colors": [], "stats": {}, "mood": []}


# ───────────────────────── 3) أرقام السوق (يوتيوب) ─────────────────────────

def _yt_search(query: str, gl: str = "US", hl: str = "en") -> list:
    """أكثر الفيديوهات مشاهدة لكلمة بحث — من صفحة نتائج يوتيوب نفسها (ترتيب المشاهدات)."""
    url = ("https://www.youtube.com/results?" +
           urllib.parse.urlencode({"search_query": query, "sp": "CAMSAhAB", "gl": gl, "hl": hl}))
    html = _get(url, timeout=25).decode("utf-8", "ignore")
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        raise RuntimeError("مفيش نتائج (يمكن الصفحة اتغيّرت أو الطلب اتمنع)")
    data = json.loads(m.group(1))
    out = []

    def walk(node):
        if isinstance(node, dict):
            if "videoRenderer" in node:
                v = node["videoRenderer"]
                title = "".join(t.get("text", "") for t in (v.get("title", {}).get("runs") or [])) \
                    or v.get("title", {}).get("simpleText", "")
                views = (v.get("viewCountText", {}) or {}).get("simpleText", "") \
                    or "".join(t.get("text", "") for t in (v.get("viewCountText", {}).get("runs") or []))
                out.append({"id": v.get("videoId"), "title": title, "views_text": views,
                            "published": (v.get("publishedTimeText", {}) or {}).get("simpleText", ""),
                            "channel": (v.get("ownerText", {}) or {}).get("runs", [{}])[0].get("text", ""),
                            "duration": (v.get("lengthText", {}) or {}).get("simpleText", "")})
            for val in node.values():
                walk(val)
        elif isinstance(node, list):
            for val in node:
                walk(val)

    walk(data)
    return out[:12]


def _views_number(txt: str) -> int:
    t = (txt or "").lower().replace(",", "").replace("views", "").replace("view", "").strip()
    mult = 1
    for suf, m in (("b", 10 ** 9), ("m", 10 ** 6), ("k", 10 ** 3)):
        if suf in t:
            mult = m
            t = t.replace(suf, "")
            break
    try:
        return int(float(re.sub(r"[^0-9.]", "", t) or 0) * mult)
    except Exception:
        return 0


# ─────────────────── المرجع البصري ⇒ إعدادات المونتاج ───────────────────
# Pinterest وأمثاله **مرجع بصري بس**: بنقرأ المزاج/الألوان/التكوين/الحركة ونحوّلهم
# لإعدادات عندنا (مظهر · كاميرا · مشاهد · موسيقى · مؤثرات) — ومفيش أي ملف منهم يدخل الفيديو.

RECIPES = {
    "rain": dict(look="cinema_cool", moves=["drift_up", "zoom_in", "still"],
                 scenes=["rain_glass", "ocean", "valley_lake", "snow_pines", "neon_rain"],
                 music="night_drone", palette=["#0b1a2a", "#1d3b53", "#7fa6c4"],
                 mood="هدوء وسكون · ليل ممطر"),
    "sleep": dict(look="cinema_night", moves=["still", "drift_up", "zoom_in"],
                  scenes=["starfield", "ocean", "rain_glass", "aurora", "bubble_lamp"],
                  music="warm_pad", palette=["#080d1a", "#1b2a4a", "#c8b98a"],
                  mood="دفء ونوم · إضاءة خفيفة"),
    "night": dict(look="cinema_night", moves=["still", "drift_up", "pan_right"],
                  scenes=["starfield", "aurora", "dunes_moon", "rain_glass"],
                  music="lofi_keys", palette=["#0a0e1e", "#243b6b", "#ffd9a0"],
                  mood="سحر الليل · عمق"),
    "fireplace": dict(look="cinema_warm", moves=["zoom_in", "still", "drift_up"],
                      scenes=["fireplace", "dunes_moon", "candle_desk"],
                      music="warm_pad", palette=["#1a0d06", "#7a3b12", "#ffb347"],
                      mood="دفء وجود"),
    "satisfying": dict(look="satisfying", moves=["zoom_in", "pan_left", "pan_right"],
                       scenes=["sand_table", "pendulum_wave", "harmonograph", "zen_garden"],
                       music="dream_pulse", palette=["#f2f2f2", "#8fd3ff", "#ffd166"],
                       mood="نظافة وتكرار مريح"),
    "kinetic": dict(look="satisfying", moves=["pan_left", "zoom_in", "pan_right"],
                    scenes=["sand_table", "pendulum_wave"],
                    music="lofi_keys", palette=["#eee6d8", "#7a5c3e", "#3aa6a0"],
                    mood="رمل سينمائي · تكرار"),
    "cozy": dict(look="cinema_warm", moves=["drift_up", "still", "zoom_in"],
                 scenes=["fireplace", "dunes_moon", "rain_glass", "candle_desk"],
                 music="lofi_keys", palette=["#211409", "#a86a3a", "#ffe0b2"],
                 mood="كوفي دافئ · راحة"),
    "focus": dict(look="cinema_cool", moves=["still", "drift_up", "pan_left"],
                  scenes=["starfield", "ocean", "planet_rings", "rain_glass", "bubble_lamp"],
                  music="harp_mist", palette=["#0c1220", "#2b3f63", "#9fb4d8"],
                  mood="تركيز طويل · بلا تشتيت"),
    "story": dict(look="story", moves=["zoom_in", "pan_right", "drift_up"],
                  scenes=["valley_lake", "dunes_moon", "snow_pines", "aurora", "zen_garden", "candle_desk"],
                  music="music_box", palette=["#1b1230", "#6a4fb6", "#ffe9a8"],
                  mood="حكاية بلا كلام · دفء"),
    "ocean": dict(look="cinema_cool", moves=["pan_left", "zoom_out", "drift_up"],
                  scenes=["ocean", "valley_lake"], music="night_drone",
                  palette=["#04121f", "#0d4f6b", "#9fe3ff"], mood="موج وأفق"),
    "space": dict(look="cinema_night", moves=["zoom_out", "still", "drift_up"],
                  scenes=["starfield", "planet_rings", "aurora"], music="cosmic_pad",
                  palette=["#05060f", "#3a2a6b", "#cfe0ff"], mood="فَضاء وسكون"),
    "zen": dict(look="clean", moves=["still", "drift_up", "pan_right"],
                scenes=["zen_garden", "harmonograph", "sand_table"],
                music="glass_garden", palette=["#e9e4d6", "#8fb9a8", "#3d5a4c"],
                mood="جنينة زن · سكون مرتب"),
    "candle": dict(look="cinema_warm", moves=["zoom_in", "still", "drift_up"],
                   scenes=["candle_desk", "fireplace"], music="warm_pad",
                   palette=["#140d08", "#7a4a1e", "#ffc477"], mood="ضوء شمعة · دفء هادي"),
    "neon": dict(look="cinema_cool", moves=["pan_left", "zoom_in", "drift_up"],
                 scenes=["neon_rain", "rain_glass"], music="city_night",
                 palette=["#070a16", "#2a2f6b", "#ff5fa2"], mood="ليل مدينة · نيون ومطر"),
    "bubbles": dict(look="cinema_cool", moves=["drift_up", "still", "zoom_in"],
                    scenes=["bubble_lamp", "ocean"], music="ocean_lullaby",
                    palette=["#04101f", "#1b4b6b", "#bfe9ff"], mood="فقاعات صاعدة · سكون مضيء"),
}


# ───────── 3) مصادر بلا مفتاح: ريدت (طلب حقيقي) + ويكيميديا (مراجع) ─────────
# كلها APIs عامة **بلا مفتاح** ⇒ المصنع بيشتغل من غير ما حد يعمله حاجة.

def _key(*names) -> str:
    """يقرا أول مفتاح موجود من البيئة (بيدعم كل صيغ الأسماء المستخدمة عندنا)."""
    import os
    for n in names:
        v = os.environ.get(n)
        if v:
            return v.strip()
    return ""


def reddit_demand(subs=("oddlysatisfying", "rainsounds", "ambient", "SleepingTime", "studying"),
                  limit: int = 12) -> dict:
    """
    طلب حقيقي من الجمهور: أعلى المنشورات في مجتمعاتنا (Reddit عام، بلا مفتاح).
    اللي الناس بتعمله upvote بيدّينا إشارة مزاج/موضوع مش موجودة في أرقام يوتيوب.
    """
    out, errors = {}, []
    for sub in subs:
        try:
            url = f"https://www.reddit.com/r/{sub}/top.json?t=month&limit={limit}"
            d = json.loads(_get(url, timeout=20).decode("utf-8", "ignore"))
            posts = [c["data"] for c in d["data"]["children"]]
            out[sub] = [{"title": x.get("title", "")[:110], "score": int(x.get("score", 0)),
                         "comments": int(x.get("num_comments", 0)),
                         "ratio": round(float(x.get("upvote_ratio", 0)), 3)} for x in posts]
        except Exception as e:
            errors.append(f"reddit/{sub}: {type(e).__name__}")
    # موضوعات سايدة: كلمات متكرّرة في أعلى 5 منشورات
    words = {}
    for sub, posts in out.items():
        for p in posts[:5]:
            for w in re.findall(r"[a-zA-Z]{4,}", p["title"].lower()):
                if w not in ("this", "that", "with", "from", "they", "have", "just", "what", "when",
                             "your", "will", "been", "were", "into", "very", "more", "than", "some"):
                    words[w] = words.get(w, 0) + p["score"]
    doc = {"subs": out, "topics": dict(sorted(words.items(), key=lambda kv: -kv[1])[:14]),
           "errors": errors, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return doc


def youtube_suggest(seed: str, gl: str = "us", hl: str = "en") -> list:
    """اقتراحات البحث الحقيقية بتاعة يوتيوب (بلا مفتاح) — الناس بتدوّر على إيه بالحرف."""
    try:
        q = urllib.parse.urlencode({"client": "firefox", "ds": "yt", "hl": hl, "gl": gl, "q": seed})
        data = json.loads(_get(f"https://suggestqueries.google.com/complete/search?{q}", timeout=15)
                          .decode("utf-8", "ignore"))
        return [str(x) for x in (data[1] if len(data) > 1 else []) if x]
    except Exception:
        return []


SEARCH_SEEDS = {
    "sleep": ["rain sounds", "sleep sounds", "black screen sleep", "10 hours rain", "brown noise"],
    "focus": ["study with me", "focus music", "brown noise focus", "concentration sounds"],
    "satisfying": ["satisfying video", "kinetic sand", "oddly satisfying", "satisfying loop"],
    "story": ["wordless animation", "animated short no dialogue", "bedtime story animation"],
}


def search_demand(gl: str = "us", hl: str = "en") -> dict:
    """
    طلب البحث الحقيقي: بنسأل يوتيوب «الناس بتكتب إيه؟» لكل تخصص بتاعنا.
    النتيجة بتتحفظ وتتغذّى للعقل + بتستخدم في الكلمات المفتاحية للفيديوهات.
    """
    out, errors, by_pillar = {}, [], {}
    for pillar, seeds in SEARCH_SEEDS.items():
        got = {}
        for sd in seeds:
            for i, phrase in enumerate(youtube_suggest(sd, gl=gl, hl=hl)[:10]):
                p_ = phrase.strip().lower()
                if not p_:
                    continue
                got[p_] = got.get(p_, 0) + max(1, 11 - i)          # الأقرب للكلمة = أقوى
        out[pillar] = dict(sorted(got.items(), key=lambda kv: -kv[1])[:14])
        by_pillar[pillar] = list(out[pillar])[:6]
    doc = {"by_pillar": out, "top": by_pillar, "errors": errors,
           "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return doc


def phrases_for(pillar: str, n: int = 6) -> list:
    """أقوى عبارات البحث الحقيقية للتخصص (تستخدمها العناوين والوسوم)."""
    doc = _jload(STATE / "trends.json", {}) or {}
    sd = (doc.get("search_demand") or {}).get("by_pillar", {}).get(pillar)
    if not sd:
        sd = search_demand()["by_pillar"].get(pillar, {})
    return list(sd)[:n] if isinstance(sd, dict) else list(sd)[:n]


def wikimedia_refs(query: str, limit: int = 4) -> list:
    """صور مرجعية من ويكيميديا كومنز (بلا مفتاح) — **مرجع بصري بس** زي أي لوحة تانية."""
    try:
        q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search",
                                    "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": limit,
                                    "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 480})
        d = json.loads(_get(f"https://commons.wikimedia.org/w/api.php?{q}", timeout=20).decode("utf-8"))
        items = []
        for page in (d.get("query", {}).get("pages", {}) or {}).values():
            ii = (page.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata", {})
            items.append({"source": "wikimedia", "title": page.get("title", "")[5:80],
                          "creator": (meta.get("Artist", {}) or {}).get("value", "")[:60],
                          "license": (meta.get("LicenseShortName", {}) or {}).get("value", "?"),
                          "url": ii.get("descriptionurl"), "thumb": ii.get("thumburl")})
        return [i for i in items if i.get("thumb")]
    except Exception:
        return []


def trends_v2(apply_to_brain: bool = False, use_reddit: bool = True) -> dict:
    """صورة الطلب الكاملة: يوتيوب (مشاهدات) + بحث حقيقي (اقتراحات) + ريدت (تفاعل)."""
    doc = trends(apply_to_brain=False)
    try:
        sd = search_demand()
        doc["search_demand"] = sd
        # تغذية مباشرة: عبارات النوم اللي فيها «no ads / black screen / for sleeping» = طلب مؤكد
        boost = {"sleep": 0, "focus": 0}
        for pillar in ("sleep", "focus"):
            for ph in sd["by_pillar"].get(pillar, {}):
                if any(k in ph for k in ("no ads", "black screen", "for sleeping", "for studying", "brown noise")):
                    boost[pillar] += 1
        doc["search_boost"] = boost
    except Exception as e:
        doc.setdefault("errors", []).append(f"suggest: {type(e).__name__}")
    if use_reddit:
        try:
            rd = reddit_demand()
            doc["reddit"] = {"subs": {k: len(v) for k, v in rd["subs"].items()},
                             "topics": rd["topics"], "errors": rd["errors"]}
            for t, score in list(rd["topics"].items())[:10]:      # إشارة إضافية للطلب
                if t in doc.get("demand", {}):
                    doc["demand"][t] = doc["demand"][t] + min(6, int(score / 20000))
        except Exception as e:
            doc.setdefault("errors", []).append(f"reddit: {type(e).__name__} (بعض السيرفرات بتحجب ريدت — عادي)")
    _jdump(STATE / "trends.json", doc)
    if apply_to_brain:
        doc["brain"] = apply_to_brain_from(doc)
    return doc


def look_recipe(topic: str, save: bool = True) -> dict:
    """يحوّل مرجع بصري (كلمة/جملة) لإعدادات مونتاج عندنا — قواعد ثابتة بلا إنترنت."""
    q = (topic or "").lower()
    hits = [k for k in RECIPES if k in q]
    if not hits:                                  # مطابقة حروف أولى لو مفيش تطابق كامل
        hits = [k for k in RECIPES if any(w[:4] == k[:4] for w in re.split(r"\W+", q) if w)]
    base = RECIPES[hits[0]] if hits else RECIPES.get("cozy")
    rec = {
        "query": topic,
        "matched": hits or ["cozy"],
        "look": base["look"], "moves": list(base["moves"]), "scenes": list(base["scenes"]),
        "music": base["music"], "palette": list(base["palette"]), "mood": base["mood"],
        "pinterest": pinterest_links(topic)[:3],
        "note": "مرجع بصري فقط (Pinterest/Openverse) — الملفات المولّدة كلها من عندنا",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if save:
        doc = _jload(STATE / "refs.json", {}) or {}
        recs = doc.setdefault("recipes", {})
        recs[topic] = rec
        doc["recipes_updated"] = rec["at"]
        _jdump(STATE / "refs.json", doc)
    return rec


def recipe_for(pillar: str) -> dict:
    """أفضل إعداد مونتاج للتخصص: من قواعد المرجع + لوحة الألوان المحلّلة + أقرب لوحة محفوظة."""
    rec = look_recipe(pillar, save=False)
    pal = palette_for(pillar, live=False)
    if pal.get("colors"):
        rec["palette"] = pal["colors"]              # ألوان حقيقية من تحليل المراجع
        rec["palette_source"] = pal.get("source")
        rec["ref_mood"] = pal.get("mood")
    doc = _jload(STATE / "refs.json", {}) or {}
    boards = doc.get("boards") or []
    for b in boards:
        if pillar.lower() in json.dumps(b, ensure_ascii=False).lower():
            rec["board"] = b.get("query")
            rec["refs_saved"] = b.get("saved")
            break
    return rec


def trends(queries=None, apply_to_brain: bool = False) -> dict:
    """يجيب أعلى الفيديوهات مشاهدة في تخصصاتنا ويكتب `state/trends.json` (+ يغذّي العقل)."""
    queries = queries or NICHES
    result, errors = {}, []
    for q in queries:
        try:
            rows = _yt_search(q)
            for r in rows:
                r["views"] = _views_number(r.get("views_text", ""))
            rows = sorted(rows, key=lambda r: -r["views"])
            result[q] = {"top": rows[:8], "top_views": rows[0]["views"] if rows else 0}
        except Exception as e:
            errors.append(f"{q[:32]}: {type(e).__name__}")
    demand: dict = {}
    for q, d in result.items():
        for r in d["top"]:
            for pillar, keys in PILLAR_KEYS.items():
                if any(k in (r["title"] or "").lower() for k in keys):
                    demand[pillar] = demand.get(pillar, 0) + 1
    doc = {"checked": datetime.now(timezone.utc).isoformat(), "queries": result,
           "demand": dict(sorted(demand.items(), key=lambda kv: -kv[1])), "errors": errors,
           "note": "أرقام يوتيوب حقيقية (ترتيب المشاهدات) — بتغذّي خطة المصنع."}
    _jdump(STATE / "trends.json", doc)
    if apply_to_brain:
        doc["brain"] = apply_to_brain_from(doc)
    return doc


def demand() -> dict:
    """ترتيب الطلب الحقيقي (من آخر بحث سوق) — يستخدمه المصنع في توزيع الأنواع."""
    return (_jload(STATE / "trends.json", {}) or {}).get("demand", {})


def apply_to_brain_from(doc: dict, max_nudge: float = 0.18) -> dict:
    """يعدّل أوزان العقل بلطف على حساب الطلب الحقيقي (مش بيقلب الخطط — بيمايلها)."""
    try:
        from engine import agent
    except Exception as e:
        return {"applied": False, "reason": type(e).__name__}
    dem = doc.get("demand") or {}
    if not dem:
        return {"applied": False, "reason": "مفيش طلب واضح"}
    try:
        b = agent.Brain.load()
    except Exception:
        return {"applied": False, "reason": "مفيش عقل محفوظ"}
    total = sum(dem.values()) or 1
    touched = {}
    for pillar, cnt in dem.items():
        share = cnt / total
        nudge = 1.0 + max_nudge * (share - 1.0 / max(len(dem), 1))
        b.weights.setdefault("pillar", {})
        b.weights["pillar"][pillar] = round(b.weights["pillar"].get(pillar, 1.0) * nudge, 4)
        touched[pillar] = b.weights["pillar"][pillar]
    b.save()
    return {"applied": True, "weights": touched}


# ───────────────────────── CLI ─────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="مراجع بصرية + أرقام السوق")
    ap.add_argument("--board", metavar="QUERY")
    ap.add_argument("--pinterest", metavar="QUERY")
    ap.add_argument("--trends", action="store_true")
    ap.add_argument("--trends2", action="store_true", help="يوتيوب + ريدت (طلب أدق)")
    ap.add_argument("--reddit", action="store_true", help="طلب حقيقي من مجتمعاتنا (بلا مفتاح)")
    ap.add_argument("--recipe", metavar="TOPIC", help="تحويل مرجع بصري لإعدادات مونتاج")
    ap.add_argument("--analyze", metavar="TOPIC", help="تحليل صور المراجع ⇒ لوحة ألوان حقيقية")
    ap.add_argument("--apply", action="store_true", help="يغذّي العقل بلطف")
    ap.add_argument("--limit", type=int, default=8)
    a = ap.parse_args()
    if a.board:
        d = board(a.board, a.limit)
        print(f"🖼️ لوحة «{a.board}»: {d['saved']} صورة مرجعية · {len(d['pinterest'])} رابط Pinterest")
        print("   القاعدة:", d["rule"])
        for i in d["pinterest"][:3]:
            print("   •", i["label"], "→", i["url"])
        if d["errors"]:
            print("   ملاحظات:", d["errors"])
    if a.pinterest:
        for i in pinterest_links(a.pinterest):
            print("•", i["label"], "→", i["url"])
    if a.analyze:
        r = analyze_refs(a.analyze)
        print(f"🎨 تحليل «{a.analyze}»: {r['images']} صورة مرجعية")
        print(f"   الألوان: {r['palette']}")
        print(f"   إحصاءات: {r['stats']}")
        print(f"   المزاج: {' · '.join(r['mood']) or '—'}")
    if a.recipe:
        r = look_recipe(a.recipe)
        print(f"🎬 وصفة المونتاج «{a.recipe}»: مظهر={r['look']} · موسيقى={r['music']} · "
              f"كاميرا={r['moves']} · مشاهد={r['scenes']} · مزاج={r['mood']}")
    if a.reddit:
        r = reddit_demand()
        print("👥 مواضيع سايدة (Reddit · بلا مفتاح):")
        for t, sc in list(r["topics"].items())[:10]:
            print(f"   • {t:18s} {sc:,}")
    if a.trends2:
        d = trends_v2(apply_to_brain=a.apply)
        print("📈 يوتيوب:", {k: (v["top"][0]["views_text"] if v.get("top") else "—") for k, v in d["queries"].items()})
        print("👥 ريدت:", d.get("reddit", {}).get("topics", {}))
        print("   الطلب:", d["demand"])
        if a.apply:
            print("   تغذية العقل:", d.get("brain"))
    if a.trends:
        d = trends(apply_to_brain=a.apply)
        print("📈 أعلى مشاهدات في تخصصاتنا:")
        for q, v in d["queries"].items():
            top = v["top"][0] if v["top"] else {}
            print(f"   • {q[:44]:46s} {top.get('views_text','—'):>14s}  {str(top.get('title',''))[:44]}")
        print("   الطلب:", d["demand"])
        if a.apply:
            print("   تغذية العقل:", d.get("brain"))
        if d["errors"]:
            print("   تعذّر بعض البحث:", d["errors"])
