"""
🎵 محرّك الموسيقى والمؤثرات الحقيقية — أصوات وموسيقى من مكتبات حرة (آمنة للربح)
================================================================================
ليه كده؟ لأن **الموسيقى المشهورة من يوتيوب = كليمة حقوق ⇒ إيقاف الربح/حذف القناة**.
فبدلًا منها بنجيب **موسيقى حقيقية مرخّصة** بنفس الإحساس/المزاج المطلوب:

    • Openverse Audio   — بلا مفتاح · فلترة رخصة (CC0/PD أولوية ثم CC-BY)
    • Wikimedia Commons — ملفات صوتية حرة (PD/CC)
    • Internet Archive  — تسجيلات ملكية عامة
    • Jamendo           — موسيقى فنانين برخص CC (بنفلتر: ممنوع NC/ND)

كل مقطع بنسجّل رخصته ومصدره، وبنحط الكريديت في وصف الفيديو ⇒ ربح آمن 100%.

التشغيل:
    from engine import music
    tr = music.track_for("sleep_ambience", seed=7, seconds=30)
    music.credits([tr])          # سطور الوصف
    music.decode(tr["path"], 30) # مصفوفة ستيريو للمزج
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

from engine import proc

# ⚠️ الكاش خارج الورك سبيس (ملفات صوت كبيرة · الورك سبيس محدود)
CACHE = pathlib.Path(os.environ.get("DOLLARS_MUSIC_CACHE") or (pathlib.Path(tempfile.gettempdir()) / "dollars_music"))
UA = {"User-Agent": "DollarsStudio/1.0 (+https://github.com/DawshaX/Dollars)"}
MAX_MB = 40
SR = 44100

# 🎼 مزاج كل نوع → كلمات بحث تعطي إحساس «المشهور» بنفس الجو (بلا حقوق)
MOODS = {
    "sleep_ambience": ["ambient sleep drone", "calm ambient pad", "night ambient music"],
    "focus_study": ["lofi study music", "ambient focus music", "minimal piano study"],
    "satisfying": ["lofi chill", "chillhop instrumental", "soft electronic background"],
    "facts": ["cinematic documentary music", "curious playful background", "inspiring piano"],
    "space_nature": ["cinematic space ambient", "epic ambient soundtrack", "orchestral ambient"],
    "fun_memes": ["quirky comedy background", "funny upbeat music", "playful cartoon music"],
    "story": ["emotional piano story", "fairytale music box", "gentle orchestral"],
    "calm_wellness": ["healing ambient music", "meditation calm music", "spa relaxation music"],
    "asmr": ["asmr soft ambience", "soft whisper ambience", "relaxing tapping sounds"],
    "comfort_relax": ["cozy warm piano", "comfort ambient music", "warm lofi calmer"],
    "funny": ["comedy upbeat background", "quirky cartoon music", "happy playful game music"],
    "rain_nature": ["rain ambience music", "nature sounds relaxing music"],
}

# رخص ممنوعة صراحة للربح
BAD_LICENSE = ("nc", "nd", "noncommercial", "noderiv", "-nc", "-nd", "sampling+")


def _json(url: str, headers: dict | None = None, timeout: int = 25):
    try:
        req = urllib.request.Request(url, headers={**UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        return None


def _license_ok(lic: str, url: str = "") -> bool:
    """نقبل: CC0 · Public Domain · CC-BY · CC-BY-SA. نرفض: NC · ND · مش معروف."""
    s = f"{lic or ''} {url or ''}".lower()
    if any(b in s for b in BAD_LICENSE):
        return False
    if any(k in s for k in ("cc0", "publicdomain", "public domain", "pdm", "cc-by", "by/",
                            "attribution", "cc by", "bysa", "by-sa")):
        return True
    return False


def _needs_credit(lic: str, url: str = "") -> bool:
    s = f"{lic or ''} {url or ''}".lower()
    return not any(k in s for k in ("cc0", "publicdomain", "public domain", "pdm"))


# ─────────────────────────── المصادر ───────────────────────────

def openverse(query: str, per: int = 4, min_seconds: float = 30) -> list[dict]:
    """Openverse Audio — بلا مفتاح (ويفضّل cc0/pdm أولًا)."""
    out = []
    for lic in ("cc0,pdm", "by,by-sa"):
        u = ("https://api.openverse.org/v1/audio/?q=" + urllib.parse.quote(query) +
             f"&page_size={max(2, per)}&license={lic}&duration=short,medium,long")
        d = _json(u) or {}
        for r in (d.get("results") or []):
            secs = (r.get("duration") or 0) / 1000.0
            if secs and secs < min_seconds:
                continue
            url = r.get("url") or ""
            if not url.lower().endswith((".mp3", ".ogg", ".wav", ".flac")):
                continue
            if not _license_ok(r.get("license"), r.get("license_url") or ""):
                continue
            out.append({"source": "openverse/" + str(r.get("provider") or "?"), "id": str(r.get("id")),
                        "title": r.get("title") or "", "creator": r.get("creator") or "",
                        "tags": [str(t.get("name") if isinstance(t, dict) else t) for t in (r.get("tags") or [])],
                        "license": (r.get("license") or "").upper() + " " + str(r.get("license_version") or ""),
                        "license_url": r.get("license_url") or "",
                        "page": r.get("foreign_landing_url") or r.get("detail_url") or "",
                        "url": url, "seconds": secs or None,
                        "needs_credit": _needs_credit(r.get("license"), r.get("license_url") or "")})
        if len(out) >= per:
            break
    return out


def wikimedia_audio(query: str, per: int = 3, min_seconds: float = 30) -> list[dict]:
    """صوت من ويكيميديا كومونز (موسيقى/أجواء) — بلا مفتاح."""
    u = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search"
         "&gsrsearch=" + urllib.parse.quote(f"{query} filetype:audio") +
         f"&gsrnamespace=6&gsrlimit={max(2, per * 2)}&prop=imageinfo&iiprop=url|mime|size|extmetadata")
    d = _json(u) or {}
    out = []
    for p in ((d.get("query") or {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        url = ii.get("url") or ""
        mime = (ii.get("mime") or "")
        if not url.lower().endswith((".ogg", ".oga", ".mp3", ".wav", ".flac", ".opus")):
            continue
        if "video" in mime or "image" in mime:
            continue
        ext = (ii.get("extmetadata") or {})
        lic = ((ext.get("LicenseShortName") or {}).get("value") or "")
        if not _license_ok(lic, url):
            continue
        out.append({"source": "wikimedia", "id": str(p.get("pageid")), "title": (p.get("title") or "")[5:],
                    "creator": ((ext.get("Artist") or {}).get("value") or "")[:90],
                    "license": lic, "license_url": ((ext.get("LicenseUrl") or {}).get("value") or ""),
                    "page": ii.get("descriptionurl") or "", "url": url, "seconds": None,
                    "needs_credit": _needs_credit(lic, url)})
        if len(out) >= per:
            break
    return out


def archive_audio(query: str, per: int = 3, min_seconds: float = 30) -> list[dict]:
    """Internet Archive — تسجيلات ملكية عامة (بلا مفتاح)."""
    q = (f'mediatype:audio AND ({query}) AND (licenseurl:*publicdomain* OR '
         f'licenseurl:*creativecommons* OR rights:*public domain*)')
    d = _json("https://archive.org/advancedsearch.php?q=" + urllib.parse.quote(q) +
              "&fl[]=identifier&fl[]=title&fl[]=creator&fl[]=licenseurl&rows=" + str(max(2, per)) +
              "&output=json") or {}
    out = []
    for doc in ((d.get("response") or {}).get("docs") or [])[:per]:
        ident = doc.get("identifier")
        if not ident:
            continue
        m = _json(f"https://archive.org/metadata/{ident}") or {}
        files = [f for f in (m.get("files") or [])
                 if str(f.get("name", "")).lower().endswith((".mp3", ".ogg", ".flac", ".wav"))
                 and 2e5 < float(f.get("size") or 0) < MAX_MB * 1e6]
        if not files:
            continue
        f0 = sorted(files, key=lambda f: -float(f.get("size") or 0))[0]
        lic = doc.get("licenseurl") or ""
        out.append({"source": "archive", "id": ident, "title": doc.get("title") or "",
                    "creator": doc.get("creator") or "", "license": "public domain" if "publicdomain" in lic.lower() else "CC",
                    "license_url": lic, "page": f"https://archive.org/details/{ident}",
                    "url": f"https://archive.org/download/{ident}/{urllib.parse.quote(f0['name'])}",
                    "seconds": None, "needs_credit": "publicdomain" not in lic.lower()})
    return out


def jamendo(query: str, per: int = 3, min_seconds: float = 30) -> list[dict]:
    """Jamendo — موسيقى فنانين برخص CC (بنرفض NC/ND). مفتاح تجريبي عام."""
    cid = os.environ.get("JAMENDO_CLIENT_ID") or "56d30c95"
    u = (f"https://api.jamendo.com/v3.0/tracks/?client_id={cid}&format=json&limit={max(2, per * 2)}"
         f"&search={urllib.parse.quote(query)}&audioformat=mp32&include=licenses")
    d = _json(u) or {}
    out = []
    for r in (d.get("results") or []):
        lic = (r.get("license_ccurl") or "")
        if not _license_ok("cc-by" if "by" in lic else lic, lic):
            continue
        if float(r.get("duration") or 0) < min_seconds:
            continue
        out.append({"source": "jamendo", "id": str(r.get("id")), "title": r.get("name") or "",
                    "creator": r.get("artist_name") or "", "license": "CC-BY",
                    "license_url": lic, "page": r.get("shareurl") or "",
                    "url": r.get("audio") or "", "seconds": float(r.get("duration") or 0),
                    "needs_credit": True})
        if len(out) >= per:
            break
    return out


# ─────────────────────────── التنزيل والمزج ───────────────────────────

def trim_cache(max_mb: int = 120, keep_min: int = 4) -> int:
    """يقصّ كاش الأصوات (الأقدم الأول) — ممنوع نعدّي مساحة السيرفر."""
    if not CACHE.exists():
        return 0
    files = sorted(CACHE.glob("*"), key=lambda f: f.stat().st_mtime)
    total = sum(f.stat().st_size for f in files if f.is_file()) / 1e6
    freed = 0
    for f in files:
        if not f.is_file() or total <= max_mb or len(files) - freed <= keep_min:
            break
        try:
            total -= f.stat().st_size / 1e6
            f.unlink()
            freed += 1
        except Exception:
            pass
    return freed


def download(item: dict, timeout: int = 120, min_bytes: int = 50_000) -> pathlib.Path | None:
    """ينزّل المقطع الصوتي ويتأكد إنه **صوت حقيقي** (مدة + مستوى صوت)."""
    url = item.get("url") or ""
    if not url:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    ext = pathlib.Path(urllib.parse.urlparse(url).path).suffix.lower() or ".mp3"
    p = CACHE / (hashlib.md5(url.encode()).hexdigest()[:16] + ext)
    if p.exists() and p.stat().st_size >= min_bytes:
        item["path"] = str(p)
        return p
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(MAX_MB * 1024 * 1024 + 1)
        if len(raw) > MAX_MB * 1024 * 1024 or len(raw) < min_bytes:
            item["rejected"] = "size"
            return None
        tmp = p.with_suffix(p.suffix + ".part")
        tmp.write_bytes(raw)
        d = probe_audio(tmp)
        _min_sec = 0.35 if min_bytes < 20_000 else 8.0            # المؤثرات القصيرة مسموحة
        if not d or d["seconds"] < _min_sec or d["rms"] < 0.0008:
            tmp.unlink(missing_ok=True)
            item["rejected"] = "silent_or_short"
            return None
        tmp.replace(p)
        item.update({"path": str(p), "seconds_checked": d["seconds"], "rms": d["rms"]})
        trim_cache()
        return p
    except Exception as e:
        item["error"] = f"{type(e).__name__}"
        return None


def probe_audio(path) -> dict | None:
    """مدة + مستوى صوت (RMS) من فكّ حقيقي للصوت."""
    try:
        r = subprocess.run([proc.FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(path),
                            "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                           capture_output=True, timeout=180)
        a = np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0
        if a.size < 8000:
            return None
        rms = float(np.sqrt((a ** 2).mean()))
        return {"seconds": round(a.size / 8000.0, 2), "rms": round(rms, 5)}
    except Exception:
        return None


def decode(path, seconds: float, sr: int = SR) -> np.ndarray | None:
    """يفكّ الصوت لستيريو float32 بالمدة المطلوبة (يلفّ المقطع لو أقصر)."""
    try:
        n = int(seconds * sr)
        r = subprocess.run([proc.FFMPEG, "-hide_banner", "-loglevel", "error", "-stream_loop", "-1",
                            "-i", str(path), "-t", f"{seconds:.2f}", "-ac", "2", "-ar", str(sr),
                            "-f", "f32le", "-"], capture_output=True, timeout=300)
        a = np.frombuffer(r.stdout, np.float32)
        if a.size < n * 2 * 0.5:
            return None
        return a[: n * 2].reshape(-1, 2).copy()
    except Exception:
        return None


# 🎬 مؤثرات حقيقية للمونتاج (بتضاف على لحظات الانتقال/الظهور)
SFX_QUERIES = {
    "whoosh": "deep whoosh transition", "pop": "pop sound effect", "click": "ui click short",
    "impact": "impact boom hit", "riser": "riser build up", "camera": "camera shutter",
    "sparkle": "magic sparkle chime", "page": "page turn sound",
}


def sfx(name: str, tries: int = 4) -> str | None:
    """يجيب **مؤثر صوتي حقيقي** مرخّص (قصير) ويرجّع مساره — أو None (نرجع للمولّد)."""
    q = SFX_QUERIES.get(name)
    if not q:
        return None
    cands = openverse(q, per=6, min_seconds=0.3)
    cands = [c for c in cands if (c.get("seconds") or 0) <= 8.0]
    cands.sort(key=lambda c: (0 if not c.get("needs_credit") else 1, abs((c.get("seconds") or 3) - 1.5)))
    for it in cands[: max(1, tries)]:
        if download(it, min_bytes=6_000):                          # ملفات المؤثرات صغيرة طبيعيًا
            return it["path"]
    return None


def _variants(q: str) -> list[str]:
    ws = q.split()
    out = [q]
    if len(ws) > 2:
        out.append(" ".join(ws[:2]))
    out.append(ws[0])
    seen, res = set(), []
    for v in out:
        if v and v.lower() not in seen:
            seen.add(v.lower())
            res.append(v)
    return res[:2]


def candidates(genre: str, per_mood: int = 4, min_seconds: float = 30) -> list[dict]:
    """مرشحون للموسيقى حسب النوع (Openverse → ويكي → أرشيف → Jamendo)."""
    moods = MOODS.get(genre) or MOODS["satisfying"]
    out: list[dict] = []
    for m in moods[:2]:
        for v in _variants(m):
            out += openverse(v, per=per_mood, min_seconds=min_seconds)
            if len(out) >= per_mood * 2:
                break
        if len(out) >= per_mood * 2:
            break
    if len(out) < 3:
        out += wikimedia_audio(moods[0], per=3, min_seconds=min_seconds)
    if len(out) < 3:
        out += archive_audio(moods[0], per=3, min_seconds=min_seconds)
    if len(out) < 3:
        out += jamendo(moods[0], per=3, min_seconds=min_seconds)
    seen, res = set(), []
    for it in out:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        res.append(it)
    return res


def _relevance(item: dict, genre: str) -> float:
    """صلة التراك بالمزاج المطلوب (بالوسوم والعنوان) — عشان ما يجيبلناش حاجة غلط."""
    words = set()
    for m in (MOODS.get(genre) or []):
        words |= {w for w in re.findall(r"[a-z]{4,}", m)}
    text = (str(item.get("title") or "") + " " + " ".join(item.get("tags") or [])).lower()
    hits = len(words & {w for w in re.findall(r"[a-z]{4,}", text)})
    dur = float(item.get("seconds") or 0)
    score = hits * 2.0
    score += 1.0 if dur >= 90 else (0.5 if dur >= 45 else 0)
    score += 1.0 if not item.get("needs_credit") else 0     # CC0 أولوية (شفافية أقل تعقيدًا)
    score += 0.5 if (item.get("creator") or "").strip() else 0
    return score


def track_for(genre: str, seed: int = 0, seconds: float = 30.0, tries: int = 4) -> dict | None:
    """يطلّع تراك موسيقى حقيقي مناسب للنوع — أو None (نرجع للموسيقى المولّدة)."""
    cands = candidates(genre, min_seconds=min(30.0, max(10.0, seconds * 0.6)))
    if not cands:
        return None
    scored = sorted(cands, key=lambda c: -_relevance(c, genre))
    for it in scored[: max(1, tries)]:
        if download(it):
            it["genre"] = genre
            it["score"] = round(_relevance(it, genre), 1)
            return it
    return None


def credits(items: list[dict]) -> list[str]:
    """سطور الحقوق للوصف (شفافية كاملة · شرط رخصة CC-BY)."""
    out = []
    for it in items or []:
        if not it or not it.get("needs_credit"):
            continue
        who = it.get("creator") or "unknown"
        line = f"• Music: “{it.get('title')}” by {who} — {it.get('license')}"
        if it.get("license_url"):
            line += f" ({it['license_url']})"
        if it.get("page"):
            line += f" — {it['page']}"
        out.append(line[:300])
    return out[:4]


def license_line(item: dict | None) -> str:
    if not item:
        return ""
    return f"{item.get('source')} · {item.get('license')} · {item.get('title')}"[:160]
