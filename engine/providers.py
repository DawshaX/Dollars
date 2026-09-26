"""
🧰 مزوّدو المحتوى — كل الـAPIs المجانية اللي المصنع بيستخدمها (مساعدات المصنع).
=============================================================================
المصنع مش لوحده: عنده **مساعدات** كتير، وكل مساعد بيزوّد حاجة حقيقية:

| المساعد | بيعمل إيه | محتاج مفتاح؟ |
|---|---|---|
| Pixabay | صور ومقاطع (رخصة حرة) للمرجع البصري والطبقات | PIXABAY_KEY |
| Pexels | صور ومقاطع (رخصة حرة) | PEXELS_API_KEY |
| Openverse | صور حرة (CC) | لا |
| Wikimedia Commons | صور حرة (موسوعية) | لا |
| NASA | صور فضاء/أرض رسمية (public domain) | NASA_API_KEY |
| GNews / Currents | أخبار وحقائق من الواقع | GNEWS_API_KEY / CURRENTS_API_KEY |
| REST Countries | بيانات بلاد حقيقية | لا (اختياري) |
| Groq / Gemini | كتابة وتطوير (عنوان · وصف · أفكار · سكربت) | GROQ_API_KEY / GEMINI_API_KEY |
| Freesound | مؤثرات/موسيقى CC0 | FREESOUND_ID + SECRET |
| YouTube Suggest | كلمات الناس بتدوّر بيها فعلاً | لا |

كل الدوال **بترجع فاضي بهدوء** لو المفتاح ناقص أو الخدمة واقعة — المصنع يكمل شغله عادي.
    from engine import providers
    providers.available()                      # مين جاهز فعلاً
    providers.pixabay_videos("rain window")    # نتايج حقيقية
    providers.llm("اكتب لي ٥ أفكار فيديو...")   # نص حقيقي من LLM
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "DollarsFactory/1.0 (+https://github.com/DawshaX/Dollars)"}
TIMEOUT = 25


def _env(*names: str) -> str:
    for n in names:
        v = (os.environ.get(n) or "").strip()
        if v:
            return v
    return ""


def _json(url: str, headers: dict | None = None, data: bytes | None = None,
          method: str | None = None) -> dict | list | None:
    """طلب HTTP بأمان: أي فشل = None (مفيش كذب ومفيش انفجار)."""
    hdrs = dict(UA)
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def keys() -> dict:
    return {
        "pixabay": _env("PIXABAY_KEY", "PIXABAY_API_KEY"),
        "pexels": _env("PEXELS_API_KEY", "PEXELS"),
        "openverse": _env("OPENVERSE_TOKEN", "OPENVERSE"),
        "nasa": _env("NASA_API_KEY", "NASA"),
        "gnews": _env("GNEWS_API_KEY"),
        "currents": _env("CURRENTS_API_KEY"),
        "groq": _env("GROQ_API_KEY"),
        "gemini": _env("GEMINI_API_KEY"),
        "freesound_id": _env("FREESOUND_ID"),
        "freesound_secret": _env("FREESOUND_SECRET"),
        "restcountries": _env("RESTCOUNTRIES_KEY", "RESTCOUNTRIES"),
        "llm_base": _env("LLM_API_BASE"),
        "llm_key": _env("LLM_API_KEY"),
        "llm_model": _env("LLM_MODEL"),
    }


def available() -> dict:
    """مين جاهز فعلاً (بالمفاتيح الموجودة) — تقرير صادق."""
    k = keys()
    free = {"openverse_no_key": True, "wikimedia": True, "youtube_suggest": True,
            "restcountries_no_key": True}
    return {name: bool(k[name]) for name in
            ("pixabay", "pexels", "openverse", "nasa", "gnews", "currents", "groq", "gemini",
             "freesound_id", "llm_base")} | free


# ───────────────────────── الصور والفيديو ─────────────────────────

def pixabay_images(q: str, per: int = 8, kind: str = "photo") -> list[dict]:
    key = keys()["pixabay"]
    if not key:
        return []
    url = (f"https://pixabay.com/api/?key={key}&q={urllib.parse.quote(q)}&per_page={per}"
           f"&image_type={kind}&safesearch=true&order=popular")
    d = _json(url) or {}
    return [{"source": "pixabay", "id": str(h.get("id")), "tags": h.get("tags", ""),
             "url": h.get("largeImageURL") or h.get("webformatURL"),
             "page": h.get("pageURL"), "w": h.get("imageWidth"), "h": h.get("imageHeight")}
            for h in (d.get("hits") or [])]


def pixabay_videos(q: str, per: int = 5) -> list[dict]:
    key = keys()["pixabay"]
    if not key:
        return []
    url = (f"https://pixabay.com/api/videos/?key={key}&q={urllib.parse.quote(q)}"
           f"&per_page={per}&safesearch=true")
    d = _json(url) or {}
    out = []
    for h in (d.get("hits") or []):
        v = (h.get("videos") or {})
        best = v.get("large") or v.get("medium") or v.get("small") or {}
        out.append({"source": "pixabay", "id": str(h.get("id")), "tags": h.get("tags", ""),
                    "url": best.get("url"), "w": best.get("width"), "h": best.get("height"),
                    "seconds": best.get("duration"), "page": h.get("pageURL")})
    return out


def pexels_images(q: str, per: int = 8) -> list[dict]:
    key = keys()["pexels"]
    if not key:
        return []
    d = _json(f"https://api.pexels.com/v1/search?query={urllib.parse.quote(q)}&per_page={per}",
              headers={"Authorization": key}) or {}
    return [{"source": "pexels", "id": str(p.get("id")), "url": (p.get("src") or {}).get("large2x"),
             "page": p.get("url"), "w": p.get("width"), "h": p.get("height"),
             "photographer": p.get("photographer")} for p in (d.get("photos") or [])]


def pexels_videos(q: str, per: int = 5) -> list[dict]:
    key = keys()["pexels"]
    if not key:
        return []
    d = _json(f"https://api.pexels.com/videos/search?query={urllib.parse.quote(q)}&per_page={per}",
              headers={"Authorization": key}) or {}
    out = []
    for v in (d.get("videos") or []):
        files = sorted(v.get("video_files") or [], key=lambda f: -(f.get("width") or 0))
        pick = next((f for f in files if (f.get("width") or 0) >= 1280), files[0] if files else {})
        out.append({"source": "pexels", "id": str(v.get("id")), "url": pick.get("link"),
                    "w": pick.get("width"), "h": pick.get("height"),
                    "seconds": v.get("duration"), "page": v.get("url")})
    return out


def openverse_images(q: str, per: int = 8) -> list[dict]:
    """صور حرة (CC) — مش محتاج مفتاح أبدًا."""
    url = (f"https://api.openverse.org/v1/images/?q={urllib.parse.quote(q)}&page_size={per}"
           "&license_type=all-cc&mature=false")
    hdr = {}
    if keys()["openverse"]:
        hdr["Authorization"] = f"Bearer {keys()['openverse']}"
    d = _json(url, headers=hdr) or {}
    return [{"source": "openverse", "id": str(r.get("id")), "url": r.get("url"),
             "page": r.get("foreign_landing_url"), "license": r.get("license"),
             "title": r.get("title")} for r in (d.get("results") or [])]


def wikimedia_images(q: str, per: int = 8) -> list[dict]:
    """صور Wikimedia Commons — حرة ومش محتاجة مفتاح."""
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search"
           f"&gsrsearch={urllib.parse.quote(q)}&gsrnamespace=6&gsrlimit={per}"
           "&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=1600")
    d = _json(url) or {}
    pages = ((d.get("query") or {}).get("pages") or {})
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata") or {}
        title = p.get("title") or ""
        low = title.lower()
        if low.endswith((".svg", ".tif", ".tiff", ".gif", ".pdf")) or not _nice_image(title):
            continue                                    # مش صورة فوتوغرافية أو فيها شرح/خريطة
        out.append({"source": "wikimedia", "id": str(p.get("pageid")), "title": title,
                    "url": ii.get("thumburl") or ii.get("url"),
                    "license": ((meta.get("LicenseShortName") or {}).get("value") or ""),
                    "page": ii.get("descriptionurl")})
    return out


# صور ممنوعة: رسومات توضيحية · خرائط · أساطير · ملصقات (مش صور حلوة)
BAD_IMAGE_WORDS = ("legend", "diagram", "chart", "infographic", "poster", "sketch", "map of",
                   "graph", "table", "schematic", "blueprint", "label", "annotated", "figure ",
                   "text graphic", "logo", "icon",
                   # صور أقمار صناعية/خرايط عليها كتابة — شكلها توضيحي مش فوتوغرافي
                   "from space", "satellite", "iss ", "spacecraft", "orbiter", "landsat",
                   "modis", "topographic", "map", "cross-section", "cutaway")


def _nice_image(title: str, desc: str = "") -> bool:
    t = f"{title} {desc}".lower()
    return not any(w in t for w in BAD_IMAGE_WORDS)


def nasa_images(q: str = "nebula", per: int = 6) -> list[dict]:
    """صور ناسا الرسمية (public domain) — بفلتر جودة (بنرفض الرسومات التوضيحية والخرايط)."""
    url = f"https://images-api.nasa.gov/search?q={urllib.parse.quote(q)}&media_type=image"
    d = _json(url) or {}
    out, seen = [], set()
    for it in ((d.get("collection") or {}).get("items") or []):
        data = (it.get("data") or [{}])[0]
        title = data.get("title") or ""
        link = ((it.get("links") or [{}])[0]).get("href")
        if not link or not _nice_image(title, data.get("description") or ""):
            continue
        if data.get("nasa_id") in seen:
            continue
        seen.add(data.get("nasa_id"))
        out.append({"source": "nasa", "id": data.get("nasa_id"), "title": title,
                    "url": link, "page": f"https://images.nasa.gov/details-{data.get('nasa_id')}"})
        if len(out) >= per:
            break
    return out


# ───────────────────────── أخبار وحقائق ─────────────────────────

def gnews(q: str, n: int = 5, lang: str = "en") -> list[dict]:
    key = keys()["gnews"]
    if not key:
        return []
    url = (f"https://gnews.io/api/v4/search?q={urllib.parse.quote(q)}&lang={lang}&max={n}"
           f"&apikey={key}")
    d = _json(url) or {}
    return [{"source": "gnews", "title": a.get("title"), "url": a.get("url"),
             "desc": (a.get("description") or "")[:300], "at": a.get("publishedAt"),
             "image": a.get("image")} for a in (d.get("articles") or [])]


def currents(q: str, n: int = 5) -> list[dict]:
    key = keys()["currents"]
    if not key:
        return []
    url = f"https://api.currentsapi.services/v1/search?keywords={urllib.parse.quote(q)}&apiKey={key}"
    d = _json(url) or {}
    return [{"source": "currents", "title": a.get("title"), "url": a.get("url"),
             "desc": (a.get("description") or "")[:300], "at": a.get("published")}
            for a in (d.get("news") or [])[:n]]


def restcountries(name: str) -> dict:
    """بيانات بلاد حقيقية (بلا مفتاح)."""
    d = _json(f"https://restcountries.com/v3.1/name/{urllib.parse.quote(name)}"
              "?fields=name,capital,population,region,languages,area,currencies,flag")
    if isinstance(d, list) and d:
        return d[0]
    return {}


def youtube_suggest(q: str, lang: str = "en") -> list[str]:
    """الكلمات اللي الناس فعلاً بتدوّر بيها على يوتيوب (مصدر مجاني ورسمي)."""
    url = ("https://suggestqueries.google.com/complete/search?client=firefox&ds=yt"
           f"&hl={lang}&q={urllib.parse.quote(q)}")
    d = _json(url)
    try:
        return list(d[1]) if isinstance(d, list) and len(d) > 1 else []
    except Exception:
        return []


# ───────────────────────── نص (LLM) ─────────────────────────

def groq(prompt: str, system: str = "", model: str = "llama-3.3-70b-versatile",
         max_tokens: int = 900, json_mode: bool = False) -> str:
    key = keys()["groq"]
    if not key:
        return ""
    body = {"model": model, "max_tokens": max_tokens,
            "messages": ([{"role": "system", "content": system}] if system else [])
                        + [{"role": "user", "content": prompt}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    d = _json("https://api.groq.com/openai/v1/chat/completions",
              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
              data=json.dumps(body).encode(), method="POST")
    try:
        return d["choices"][0]["message"]["content"]
    except Exception:
        return ""


def gemini(prompt: str, system: str = "", model: str = "gemini-2.0-flash",
           max_tokens: int = 900) -> str:
    key = keys()["gemini"]
    if not key:
        return ""
    text = (system + "\n\n" if system else "") + prompt
    body = {"contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}}
    d = _json(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
              headers={"Content-Type": "application/json"}, data=json.dumps(body).encode(), method="POST")
    try:
        return d["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return ""


def llm(prompt: str, system: str = "", **kw) -> str:
    """أي LLM متاح — Groq الأول (أسرع) وبعده Gemini وبعده أي عنوان مخصص."""
    for fn in (groq, gemini):
        out = fn(prompt, system=system, **kw)
        if out:
            return out
    base, key, model = keys()["llm_base"], keys()["llm_key"], keys()["llm_model"]
    if base and model:
        d = _json(base.rstrip("/") + "/chat/completions",
                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                  data=json.dumps({"model": model, "messages":
                                   ([{"role": "system", "content": system}] if system else [])
                                   + [{"role": "user", "content": prompt}]}).encode(), method="POST")
        try:
            return d["choices"][0]["message"]["content"]
        except Exception:
            return ""
    return ""


# ───────────────────────── صوت ─────────────────────────

def freesound(q: str, n: int = 5, license_cc0: bool = True) -> list[dict]:
    """مؤثرات/موسيقى من Freesound (بنفلتر على CC0 عشان صفر حقوق)."""
    cid, secret = keys()["freesound_id"], keys()["freesound_secret"]
    if not (cid and secret):
        return []
    tok = _json("https://freesound.org/apiv2/oauth2/access_token/",
                data=urllib.parse.urlencode({"client_id": cid, "client_secret": secret,
                                             "grant_type": "client_credentials"}).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST") or {}
    access = tok.get("access_token")
    if not access:
        return []
    filt = '&filter=license:"Creative Commons 0"' if license_cc0 else ""
    url = (f"https://freesound.org/apiv2/search/text/?query={urllib.parse.quote(q)}&page_size={n}"
           f"&fields=id,name,previews,duration,license{urllib.parse.quote(filt, safe='')}")
    d = _json(url, headers={"Authorization": f"Bearer {access}"}) or {}
    return [{"source": "freesound", "id": str(r.get("id")), "name": r.get("name"),
             "url": (r.get("previews") or {}).get("preview-hq-mp3"),
             "seconds": r.get("duration"), "license": r.get("license")}
            for r in (d.get("results") or [])]


# ───────────────────────── حقائق موثّقة (مصادر حقيقية) ─────────────────────────

def wikipedia_summary(title: str, lang: str = "en") -> dict:
    """ملخّص حقيقي من ويكيبيديا + رابط المصدر (بلا مفتاح، بلا تأليف)."""
    t = urllib.parse.quote(title.replace(" ", "_"))
    d = _json(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{t}") or {}
    if not d.get("extract"):
        return {}
    return {"title": d.get("title"), "extract": d.get("extract"),
            "url": ((d.get("content_urls") or {}).get("desktop") or {}).get("page")
                   or f"https://{lang}.wikipedia.org/wiki/{t}",
            "image": ((d.get("thumbnail") or {}).get("source")),
            "image_page": ((d.get("originalimage") or {}).get("source"))}


def wikipedia_onthisday(lang: str = "en", kind: str = "events") -> list[dict]:
    """أحداث/مواليد/وفيات حقيقية حصلت في نفس اليوم ده (بتاريخ النهاردة) + مصادرها."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    d = _json(f"https://{lang}.wikipedia.org/api/rest_v1/feed/onthisday/{kind}/{now.month}/{now.day}") or {}
    out = []
    for e in (d.get(kind) or []):
        pages = e.get("pages") or [{}]
        out.append({"text": e.get("text"), "year": e.get("year"),
                    "url": (pages[0] or {}).get("content_urls", {}).get("desktop", {}).get("page"),
                    "title": (pages[0] or {}).get("title"),
                    "image": ((pages[0] or {}).get("thumbnail") or {}).get("source")})
    return [o for o in out if o.get("text")]


def wikipedia_search(q: str, n: int = 5, lang: str = "en") -> list[dict]:
    """بحث في ويكيبيديا — عناوين حقيقية تصلح لفيديو حقائق."""
    d = _json("https://" + f"{lang}.wikipedia.org/w/api.php?action=query&format=json&list=search"
              f"&srsearch={urllib.parse.quote(q)}&srlimit={n}") or {}
    return [{"title": r.get("title"), "snippet": (r.get("snippet") or "").replace('<span class="searchmatch">', "")
             .replace("</span>", "")} for r in ((d.get("query") or {}).get("search") or [])]


def reference_visuals(topic: str, per: int = 6) -> list[dict]:
    """مرجع بصري مجمّع: بيجرّب كل المصادر الحره ويرجّع اللي نجح (ترتيب بالأفضلية)."""
    out = []
    for fn in (pixabay_images, pexels_images, openverse_images, wikimedia_images):
        try:
            got = fn(topic, per=per)
        except Exception:
            got = []
        if got:
            out.extend(got[:per])
    return out[: max(per, 12)]
