"""
🎥 محرّك الفيديو الحقيقي — مقاطع فيديو حرّة من مصادر مرخّصة تجاريًا
=====================================================================
ليه ده أحسن من الصور؟ لأن **الفيديو الحقيقي المتحرك** بيكسب:
    • نسبة إكمال أعلى (المشاهد مش حاسس إنه بيتفرج على سلايدات)
    • إحساس «محتوى حقيقي» ⇒ يوتيوب مايعتبرهوش محتوى رخيص/متكرر
    • مشاهد ناعمة أصلًا (مش كين-بيرنز مركّب على صورة ثابتة)

المصادر — كلها **رخصة تجارية حرة · بلا علامة مائية**:
    • Pexels Videos   — مجاني تجاريًا، بلا شرط ذكر (مفتاح PEXELS_API_KEY)
    • Pixabay Videos  — مجاني تجاريًا (مفتاح PIXABAY_API_KEY)
    • NASA Video      — ملكية عامة (بلا مفتاح)
    • Wikimedia Commons — CC/PD (بلا مفتاح، بنسجّل الكريديت)

التشغيل:
    from engine import clips
    items = clips.collect("ocean waves", genre="sleep_ambience")
    paths = [p for p in (clips.download(i) for i in items) if p]
    clips.render_reel(paths, "out/short.mp4", seconds=30, texts=[...])
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import random
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

from engine import grade, proc

import os
import tempfile

# ⚠️ الكاش خارج مجلد المشروع: الملفات الكبيرة ماينفعش تتخزّن في الورك سبيس (سقف صارم)
CACHE = pathlib.Path(os.environ.get("DOLLARS_CLIP_CACHE") or (pathlib.Path(tempfile.gettempdir()) / "dollars_clips"))
UA = {"User-Agent": "DollarsStudio/1.0 (+https://github.com/DawshaX/Dollars)"}
MAX_MB = 120                      # سقف حجم المقطع الواحد (نرفض الأضخم)


def _json(url: str, headers: dict | None = None, timeout: int = 30) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={**UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception:
        return None


# ─────────────────────────── جمع المقاطع ───────────────────────────

def _nasa_videos(q: str, per: int = 3) -> list[dict]:
    """فيديو ناسا — ملكية عامة ١٠٠٪ (بلا مفتاح)."""
    d = _json("https://images-api.nasa.gov/search?"
              f"q={urllib.parse.quote(q)}&media_type=video&page_size={per}") or {}
    out = []
    for it in ((d.get("collection") or {}).get("items") or [])[:per]:
        href = it.get("href")
        if not href:
            continue
        man = _json(href) or []
        mp4 = next((u for u in man if isinstance(u, str) and u.lower().endswith(".mp4")), None)
        if not mp4:
            continue
        meta = (it.get("data") or [{}])[0]
        out.append({"source": "nasa", "id": str(meta.get("nasa_id") or ""), "url": mp4,
                    "page": f"https://images.nasa.gov/details-{meta.get('nasa_id')}",
                    "seconds": None, "w": None, "h": None, "license": "public domain",
                    "title": meta.get("title") or ""})
    return out


def _wikimedia_videos(q: str, per: int = 3) -> list[dict]:
    """فيديو ويكيميديا كومونز (webm/ogv) — حرة بشرط الكريديت."""
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search"
           f"&gsrsearch={urllib.parse.quote(q + ' filetype:video')}&gsrnamespace=6&gsrlimit={per}"
           "&prop=imageinfo&iiprop=url|extmetadata|mime")
    d = _json(url) or {}
    out = []
    for p in ((d.get("query") or {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        t = (p.get("title") or "").lower()
        if not t.endswith((".webm", ".ogv", ".mp4")):
            continue
        out.append({"source": "wikimedia", "id": str(p.get("pageid")), "url": ii.get("url"),
                    "page": ii.get("descriptionurl"), "seconds": None, "w": None, "h": None,
                    "license": ((ii.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value") or "",
                    "title": p.get("title") or ""})
    return out


QW_STOP = {"close", "up", "closeup", "upclose", "video", "clip", "footage", "shot", "scene",
           "the", "and", "for", "with", "from", "high", "quality", "free", "stock", "slow",
           "motion", "macro", "closeup"}


def _qwords(s: str) -> list[str]:
    """كلمات البحث المفيدة (بدون كلمات عامة زي close up اللي بتجيب نتايج غلط)."""
    return [w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in QW_STOP]


def _variants(query: str) -> list[str]:
    """صيغ بحث متعددة لنفس الموضوع — تغطية أوسع لما المصدر ضيق."""
    q = (query or "").strip() or "nature"
    vs = [q]
    ws = q.split()
    if len(ws) > 2:
        vs.append(" ".join(ws[:2]))
        vs.append(" ".join(ws[-2:]))
    if len(ws) > 1:
        vs.append(ws[0])
    seen, out = set(), []
    for v in vs:
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out[:3]


GENRE_FALLBACK = {
    "asmr": ["water drops macro", "macro texture water", "hands close up water"],
    "comfort_relax": ["calm water surface", "clouds sky", "green leaves wind"],
    "funny": ["dog playing", "cat playing", "duck swimming"],
    "rain_nature": ["rain on window", "rain leaves", "rain puddle"],
    "sleep_ambience": ["night sky stars", "moon clouds", "candle flame"],
    "space_nature": ["earth from space", "nebula stars", "aurora"],
    "satisfying": ["sand falling slow", "paint in water", "ink in water"],
    "focus_study": ["desk laptop notes", "books library", "writing paper"],
    "facts": ["nature close up", "animals wild", "ocean waves"],
}


def collect(query: str, genre: str = "satisfying", n: int = 6,
            min_seconds: float = 2.0, min_side: int = 640,
            fallback: list[str] | None = None) -> list[dict]:
    """يجمع **مقاطع فيديو حرة** عن الموضوع من كل المصادر المتاحة (المفاتيح أولوية).

    الترتيب: Pexels · Pixabay (بمفتاح) → NASA/Archive للمواضيع الفضائية → ويكيميديا احتياطي.
    """
    from engine import providers

    q = (query or "").strip() or "nature"
    is_space = any(k in q.lower() for k in ("space", "earth", "moon", "mars", "galaxy",
                                            "rocket", "planet", "nasa", "star", "nebula"))
    out: list[dict] = []
    for v in _variants(q):
        if genre == "space_nature" or is_space:
            out += providers.nasa_videos(v, per=3) or []
            out += _nasa_videos(v, per=2)
        out += providers.pexels_videos(v, per=max(3, n)) or []
        out += providers.pixabay_videos(v, per=max(3, n)) or []
        if len(out) >= n:
            break
    if len(out) < n:                                   # ويكيميديا (بلا مفتاح · رخصة حرة)
        for v in _variants(q):
            out += _wikimedia_videos(v, per=max(2, n))
            if len(out) >= n:
                break
    if len(out) < n:                                   # Archive.org (ملكية عامة)
        for v in _variants(q):
            out += providers.archive_videos(v, per=3)
            if len(out) >= n:
                break
    # ملاحظة: ناسا بتدخل لمواضيع الفضاء بس — عشان مايحصلش عدم تطابق (فيديو أقمار لموضوع بحر!)

    clean, seen = [], set()
    for it in out:
        u = it.get("url") or ""
        if not u or u in seen:
            continue
        if (it.get("w") or 9999) < min_side and (it.get("h") or 9999) < min_side:
            continue
        secs = it.get("seconds")
        if secs is not None and float(secs) < min_seconds:
            continue
        low = u.lower()
        if any(bad in low for bad in ("watermark", "/preview", "_thumb", "sample.mp4")):
            continue
        if not title_ok(str(it.get("title") or "") + " " + urllib.parse.unquote(u)):
            continue                                   # شرح/بيانات/أخبار = مرفوض
        title = (it.get("title") or it.get("id") or "").lower()
        ql = _qwords(q)
        qw, tw = set(ql), set(re.findall(r"[a-z]{3,}", title))
        phrase = " ".join(ql[:2]) if len(ql) >= 2 else ""
        it["match"] = len(qw & tw) + (2 if phrase and phrase in title else 0)   # مطابقة الجملة = وزن أعلى
        seen.add(u)
        clean.append({**it, "needs_credit": (it.get("source") in ("wikimedia", "nasa", "archive")),
                      "credit": f"{it.get('source')}" + (f" · {it.get('license')}" if it.get("license") else "")})
    clean.sort(key=lambda x: -x.get("match", 0))       # الأقرب للموضوع الأول
    matched = [c for c in clean if c.get("match", 0) > 0]
    if len(matched) >= max(2, n // 2):                 # عندنا كفاية مطابقين ⇒ نقلل الدخلاء
        clean = matched + [c for c in clean if c.get("match", 0) == 0]
    if not matched:                                    # 🎯 مفيش مطابقة خالص ⇒ نجرب كويري احتياطي للمزاج
        _fb = list(fallback or []) + list(GENRE_FALLBACK.get(genre, []))
        for fq in _fb[:2]:
            sub = collect(fq, genre=genre, n=n, min_seconds=min_seconds, min_side=min_side)
            if any(x.get("match", 0) > 0 for x in sub):
                return sub[:n]
    return clean[:max(n, n)]


# ─────────────────────────── تنزيل + فحص ───────────────────────────

def trim_cache(max_mb: int = 300, keep_min: int = 4) -> int:
    """يقصّ كاش المقاطع (الأقدم الأول) — الورك سبيس محدود، ممنوع نعدّي السقف."""
    if not CACHE.exists():
        return 0
    files = sorted(CACHE.glob("*.mp4"), key=lambda f: f.stat().st_mtime)
    total = sum(f.stat().st_size for f in files) / 1e6
    freed = 0
    for f in files:                             # الأقدم الأول — لحد ما ننزل تحت السقف
        if total <= max_mb or len(files) - freed <= keep_min:
            break
        try:
            total -= f.stat().st_size / 1e6
            f.unlink()
            freed += 1
        except Exception:
            pass
    for part in CACHE.glob("*.part"):          # بقايا تنزيلات مقطوعة
        try:
            part.unlink()
        except Exception:
            pass
    return freed


def probe(path) -> tuple[int, int, float]:
    """(عرض, طول, ثواني) من غير ffprobe — بنقرا سطور الـffmpeg."""
    try:
        r = subprocess.run([proc.FFMPEG, "-hide_banner", "-i", str(path)],
                           capture_output=True, text=True, timeout=60)
        err = r.stderr or ""
        w = h = 0
        m = re.search(r"Stream #\d+:\d+.*?Video:.*?, (\d{2,5})x(\d{2,5})", err)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
        d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
        secs = (int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))) if d else 0.0
        return w, h, secs
    except Exception:
        return 0, 0, 0.0


def _light_urls(url: str) -> list[str]:
    """روابط أخف للديكود: نسخ ويكيميديا المضغوطة ٧٢٠/٤٨٠پ (أسرع بكتير من 4K)."""
    try:
        if "upload.wikimedia.org" in url and "/commons/" in url and "/transcoded/" not in url \
                and not re.search(r"\.(480|720|1080)p\.", url):
            base, name = url.split("?")[0].rsplit("/", 1)
            stem = name.rsplit(".", 1)[0]
            tr = base.replace("/commons/", "/commons/transcoded/")
            out = []
            for key in ("720p.vp9.webm", "480p.vp9.webm"):
                if name.lower().endswith((".webm", ".ogv", ".mp4")):   # نتحقق من الاسم الأصلي
                    out.append(f"{tr}/{name}/{stem}.{key}")
            return out
    except Exception:
        pass
    return []


def download(item: dict, timeout: int = 120, max_mb: int = MAX_MB,
             require_motion: bool = True) -> pathlib.Path | None:
    """ينزّل المقطع مرّة ويخزّنه (كاش) — بفحص حقيقي إنه فيديو سليم."""
    url = item.get("url") or ""
    if not url:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    name = hashlib.md5(url.encode()).hexdigest()[:16] + ".mp4"
    p = CACHE / name
    if p.exists() and p.stat().st_size > 60_000:
        if require_motion and item.get("quality") is None:
            item["motion"] = item.get("motion") or round(motion_score(p), 2)
            q = analyze(p)
            item["quality"] = q
            if not is_clean(q):                        # ملف قديم وحش في الكاش ⇒ يتشال
                p.unlink(missing_ok=True)
                item["rejected"] = "burned_in_text_or_graphics"
                return None
        return p
    try:
        raw = b""
        for cand in (_light_urls(url) + [url]):       # الأخف الأول
            try:
                req = urllib.request.Request(cand, headers=UA)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read(max_mb * 1024 * 1024 + 1)
                if len(raw) > max_mb * 1024 * 1024:      # ملف مقطوع ⇒ نرفضه (ديكوده ناقص)
                    raw = b""
                    continue
                if len(raw) >= 40_000:
                    item["url_used"] = cand
                    break
            except Exception:
                raw = b""
        if len(raw) < 40_000:
            item["rejected"] = "download_too_small"
            return None
        tmp = p.with_suffix(".part")
        tmp.write_bytes(raw)
        w, h, secs = probe(tmp)
        if w < 320 or h < 240 or secs < 1.0:          # مش فيديو سليم ⇒ نرفضه
            tmp.unlink(missing_ok=True)
            item["rejected"] = f"bad_video:{w}x{h}/{secs:.1f}s"
            return None
        if require_motion:
            m = motion_score(tmp)
            if m < 0.25:                      # فيديو ساكن/شبه ثابت ⇒ مرفوض
                tmp.unlink(missing_ok=True)
                item["rejected"] = f"too_still:{m:.2f}"
                return None
            item["motion"] = round(m, 2)
        if require_motion:                    # ⛔ رفض النصوص/الجرافيك المدمج (جودة + أصالة)
            q = analyze(tmp)
            item["quality"] = q
            if not is_clean(q):
                tmp.unlink(missing_ok=True)
                item["rejected"] = "burned_in_text_or_graphics"
                return None
        tmp.replace(p)
        item.update({"w": w, "h": h, "seconds": secs})
        try:
            trim_cache()
        except Exception:
            pass
        return p
    except Exception as _e:
        item["error"] = f"{type(_e).__name__}: {str(_e)[:80]}"
        return None


def motion_score(path, seconds: float = 8.0) -> float:
    """متوسط الحركة بين الكادرات (0 = صورة ساكنة تمامًا). رخيص: ١٠ كادر/ث رمادي."""
    try:
        vf = "fps=10,scale=180:320,format=gray"
        r = subprocess.run([proc.FFMPEG, "-hide_banner", "-loglevel", "error", "-i", str(path),
                            "-t", f"{seconds:.1f}", "-vf", vf, "-f", "rawvideo", "-"],
                           capture_output=True, timeout=180)
        a = np.frombuffer(r.stdout, np.uint8)
        n = len(a) // (180 * 320)
        if n < 3:
            return 0.0
        f = a[:n * 180 * 320].reshape(n, 320, 180).astype(np.float32)
        return float(np.abs(np.diff(f, axis=0)).mean())
    except Exception:
        return 0.0


def analyze(path, samples: int = 6) -> dict:
    """يفحص المقطع: فيه **نصوص/جرافيك مدمج**؟ ولا فيديو حقيقي نضيف؟

    - texty  : نسبة الصفوف في الشرايط العلوية/السفلية اللي شكلها «نص» (حواف متوسطة كتير).
    - band   : كثافة الحواف القوية في الشرايط (شرايط إخبارية/كابشن).
    - flat   : نسبة المناطق الساكنة المسطّحة (بيانات/شرايط مسطّحة = جرافيك مش فيديو).
    - sat    : متوسط التشبّع اللوني.
    """
    out = {"flat": 0.0, "band_edge": 0.0, "texty": 0.0, "sat": 0.0, "flatblk": 0.0,
           "bright": 0.0, "frames": 0}
    try:
        _, _, secs = probe(path)
        secs = secs or 4.0
        pts = [secs * (0.12 + 0.76 * (i + 0.5) / samples) for i in range(samples)]
        flats, bands, sats, blks, brs = [], [], [], [], []
        for t in pts:
            r = subprocess.run([proc.FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}",
                                "-i", str(path), "-frames:v", "1", "-vf", "scale=480:270",
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=60)
            a = np.frombuffer(r.stdout, np.uint8)
            if a.size < 480 * 270 * 3:
                continue
            fr = a[:480 * 270 * 3].reshape(270, 480, 3).astype(np.float32)
            g = fr @ np.array([0.299, 0.587, 0.114], np.float32)
            brs.append(float(g.mean()) / 255.0)
            gx = np.abs(np.diff(g, axis=1)); gy = np.abs(np.diff(g, axis=0))
            gx = np.pad(gx, ((0, 0), (0, 1))); gy = np.pad(gy, ((0, 1), (0, 0)))
            edge = np.maximum(gx, gy)
            flats.append(float((edge < 2.5).mean()))
            # نص مدمج في أي مكان: صفوف فيها حواف متوسطة كتير (شكل الحروف)
            rows_edge = (edge > 25).mean(axis=1)
            bands.append(float((rows_edge > 0.26).mean()))
            # + نص أبيض ساطع (زي خرائط/شرايط القنوات): بكسلات فاتحة جدًا وحوافها حادة
            bright = (g > 235) & (edge > 30)
            bands[-1] = max(bands[-1], float(bright.mean()) * 3.2)
            sats.append(float((fr.max(axis=2) - fr.min(axis=2)).mean()))
            _b = 8
            _H, _W = 270 // _b * _b, 480 // _b * _b
            _blk = fr[:_H, :_W].reshape(_H // _b, _b, _W // _b, _b, 3)
            _rng = _blk.max(axis=(1, 3)) - _blk.min(axis=(1, 3))
            blks.append(float((_rng.max(axis=2) <= 2).mean()))     # بلوكات ثابتة تمامًا = جرافيك
            _b2 = 24
            _H2, _W2 = 270 // _b2 * _b2, 480 // _b2 * _b2
            _blk2 = fr[:_H2, :_W2].reshape(_H2 // _b2, _b2, _W2 // _b2, _b2, 3)
            _rng2 = _blk2.max(axis=(1, 3)) - _blk2.min(axis=(1, 3))
            blks.append(float((_rng2.max(axis=2) <= 3).mean()) * 1.0)   # مساحات كبيرة مستوية
        if not flats:
            return out
        out.update(flat=round(float(np.mean(flats)), 3), band_edge=round(float(np.mean(bands)), 4),
                   texty=round(float(np.mean(bands)), 3), sat=round(float(np.mean(sats)), 1),
                   flatblk=round(float(np.mean(blks)), 3) if blks else 0.0,
                   bright=round(float(np.mean(brs)), 3) if brs else 0.0, frames=len(flats))
    except Exception as _e:
        out["error"] = f"{type(_e).__name__}"
    return out


def is_clean(q: dict) -> bool:
    """نرفض: نص مدمج · شرايط إخبارية · جرافيك بيانات مسطّح (مش فيديو حقيقي)."""
    if not q or q.get("frames", 0) < 3:                # ما قدرناش نعاين كفاية ⇒ نرفضه
        return False
    if q.get("texty", 0) > 0.09:                       # كابشن/نص مكتوب جوّه الفيديو (أي مكان)
        return False
    if q.get("flatblk", 0) > 0.40:                     # بلوكات ألوان ثابتة = جرافيك/بيانات مش كاميرا
        return False
    if q.get("flat", 0) > 0.93:                        # إطار شبه سادة (سكرين شوت/شاشة)
        return False
    if q.get("bright", 1.0) < 0.07:                    # كادر مظلم أوي — المشاهد مايشوفش حاجة
        return False
    if q.get("bright", 0.0) > 0.90 and q.get("sat", 99) < 18:
        return False                                   # مغسول أبيض بلا تفاصيل = مشهد ميّت
    if q.get("sat", 99) < 4 and q.get("flatblk", 0) > 0.25:
        return False                                   # أبيض/أسود سادة (سكرين)
    return True


# عناوين مش فيديو سينمائي: بيانات · أخبار · شروح · إعلانات
BAD_TITLE = ("band", "music video", "official video", "official audio", "lyrics", "lyric video",
             "karaoke", "cover version", "live at", "live from", "concert", "orchestra plays",
             "symphony no", "remix", "instrumental cover", "sing-along",
             "cira", "nesdis", "noaa", "meteosat", "copernicus", "goes-", "visualization",
             "visualisation", "infographic", "data ", "simulation", "animated", "animation",
             "explainer", "briefing", "press conference", "webinar", "interview", "lecture",
             "presentation", "screencast", "screen recording", "tutorial", "how to", "review",
             "vlog", "podcast", "news", "forecast", "weather", "map of", "chart", "graph",
             "diagram", "dashboard", "trailer", "teaser", "promo", "commercial", "advert",
             "conference", "panel", "speech", "update on",
             "scientific visualization", "svs2", "svs-", "render of", "cgi", "3d model",
             "artist's impression", "artist impression", "concept art", "fly-through",
             "flythrough", "schematic", "cutaway", "artist rendering",
    # 🚫 NSFW — ممنوع تمامًا من النشر
    "ejaculat",
    "orgasm",
    "masturbat",
    "porn",
    "nude",
    "naked",
    "penis",
    "vagina",
    "erotic",
    "xxx",
    "nsfw",
    "breast",
    "boob",
    "sexual",
    "fetish",
    "bikini",
    "lingerie",
    "hentai",)


NSFW_RE = re.compile(
    r"\b(ejaculat\w*|orgasm\w*|masturbat\w*|porn\w*|nude|nudity|naked|penis|vagina|erotic\w*"
    r"|xxx|nsfw|breast\w*|boob\w*|sexual\w*|fetish\w*|bikini|lingerie|hentai|viagra|condom\w*"
    r"|sperm(?!\s*whale)|strip\s*tease|sexy|topless)\b")


def title_ok(title: str) -> bool:
    """نرفض أي عنوان مش footage حقيقي (شرح · بيانات · أخبار · إعلان) أو أي محتوى NSFW."""
    t = (title or "").lower()
    if NSFW_RE.search(t):
        return False
    return not any(bad in t for bad in BAD_TITLE)


def poster(path, out_path, at: float = 0.25) -> pathlib.Path | None:
    """كادر واحد من المقطع (للأغلفة)."""
    try:
        w, h, secs = probe(path)
        ss = max(0.0, min(secs * at, max(0.0, secs - 0.2))) if secs else 0.3
        out = pathlib.Path(out_path)
        r = subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                            "-i", str(path), "-ss", f"{ss:.2f}", "-frames:v", "1", str(out)],
                           capture_output=True, timeout=90)
        return out if r.returncode == 0 and out.exists() else None
    except Exception:
        return None


def credits(items: list[dict]) -> list[str]:
    out = []
    for it in items:
        src = it.get("source", "clip")
        page = it.get("page") or ""
        lic = it.get("license") or ""
        line = f"• Video: {src}" + (f" ({lic})" if lic else "") + (f" — {page}" if page else "")
        out.append(line.strip())
    return out[:6]


# ─────────────────────────── الرندر ───────────────────────────

def _decode(path, W: int, H: int, fps: int, dur: float, start: float = 0.0):
    """يفكّ المقطع ككادرات RGB بالمقاس المطلوب (crop-fill عامودي) — generator."""
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
          f"fps={fps},format=rgb24")
    cmd = [proc.FFMPEG, "-hide_banner", "-loglevel", "error", "-stream_loop", "3",
           "-i", str(path), "-ss", f"{max(0.0, start):.2f}", "-t", f"{dur + 0.15:.2f}",
           "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = W * H * 3
    try:
        while True:
            buf = p.stdout.read(n)
            if not buf or len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    finally:
        try:
            p.stdout.close()
        except Exception:
            pass
        try:
            p.kill()
        except Exception:
            pass


def _window(fr: np.ndarray, w: int, h: int, scale: float, dx: float, dy: float) -> np.ndarray:
    """يقصّ نافذة متحرّكة من الكادر (تقريب/تحريك ناعم) ويرجّعها بمقاس الفيديو."""
    H, W = fr.shape[:2]
    cw = int(max(w, min(W, round(W / max(1.001, scale)))))
    ch = int(max(h, min(H, round(H / max(1.001, scale)))))
    cw -= cw % 2
    ch -= ch % 2
    x0 = int(np.clip((W - cw) / 2 + dx * (W - cw) / 2, 0, W - cw))
    y0 = int(np.clip((H - ch) / 2 + dy * (H - ch) / 2, 0, H - ch))
    if (cw, ch) == (w, h) and x0 == (W - cw) // 2 and y0 == (H - ch) // 2:
        return fr[y0:y0 + ch, x0:x0 + cw]
    img = Image.fromarray(fr[y0:y0 + ch, x0:x0 + cw])
    return np.asarray(img.resize((w, h), Image.BILINEAR), dtype=np.uint8)


def _split_tone_fast(f: np.ndarray, palette, strength: float = 0.42) -> np.ndarray:
    """تلوين الظلال/الإضاءة بالألوان بتاعة النوع — نسخة سريعة (بدون حساب تقيل)."""
    if not palette:
        return f
    try:
        cols = [(int(str(c).lstrip("#")[i:i + 2], 16) / 255.0) for c in palette[:3] for i in (0, 2, 4)]
        sh = np.array(cols[0:3], np.float32)
        hi = np.array(cols[-3:], np.float32)
    except Exception:
        return f
    lum = f @ np.array([0.299, 0.587, 0.114], np.float32)
    lo = np.clip(1.0 - lum * 1.8, 0, 1)[..., None]
    up = np.clip(lum * 1.8 - 0.8, 0, 1)[..., None]
    return np.clip(f + (sh - 0.5) * lo * strength * 0.30 + (hi - 0.5) * up * strength * 0.22, 0, 1)


# 🧠 مخزن مؤقت ثابت (بنعيد استخدامه) — الرام في الساندبوكس محدودة، ممنوع نسخ كتير
_SCRATCH: dict = {}


def _bufs(h: int, w: int) -> dict:
    key = (h, w)
    b = _SCRATCH.get(key)
    if b is None:
        b = {"f": np.empty((h, w, 3), np.float32), "t": np.empty((h, w, 3), np.float32),
             "lum": np.empty((h, w), np.float32)}
        if len(_SCRATCH) > 2:
            _SCRATCH.clear()
        _SCRATCH[key] = b
    return b


def _look(fr01: np.ndarray, i: int, palette, look: str, n_p: int, px, py, pv, h: int, w: int,
          body: int, calm: bool) -> np.ndarray:
    """هوية الاستوديو البصرية — نسخة **موفّرة للرام** (تعديل في المكان · بلا نسخ زايدة).

    منحنى فيلمي · تبايُن · تدرّج ألوان · تلوين نوعي · بلوم · جزيئات · فينييت · حبيبات.
    """
    from PIL import Image, ImageFilter

    # ⚠️ الحبيبات والفينييت ليهم مخزن جاهز جوه grade (مش بنعيد حسابهم كل كادر)
    if look == "warm":
        gain = np.array([1.06, 1.00, 0.94], np.float32)
        lift = np.array([0.012, 0.006, 0.0], np.float32)
    elif look == "mono":
        gain = np.array([1.02, 1.02, 1.05], np.float32)
        lift = np.array([0.004, 0.004, 0.012], np.float32)
    else:
        gain = np.array([0.96, 1.00, 1.10], np.float32)
        lift = np.array([0.008, 0.004, 0.022], np.float32)

    b = _bufs(h, w)
    f, t = b["f"], b["t"]
    if fr01.dtype == np.uint8:
        np.multiply(fr01, 1.0 / 255.0, out=f, dtype=np.float32)
    else:
        np.copyto(f, fr01, casting="unsafe")

    if look == "mono":                                   # رمادي سينمائي
        np.multiply(f, np.array([0.299, 0.587, 0.114], np.float32), out=t)
        np.sum(t, axis=2, out=b["lum"])
        f[:, :, 0] = b["lum"]
        f[:, :, 1] = b["lum"]
        f[:, :, 2] = b["lum"]

    np.multiply(f, f, out=t)                             # t = f²
    f *= -2.0
    f += 3.0                                             # f = 3-2f
    np.multiply(t, f, out=f)                             # f = f²(3-2f) منحنى ناعم
    f -= 0.5
    f *= 1.09                                            # تبايُن سينمائي
    f += 0.5
    f *= gain
    f += lift
    np.clip(f, 0, 1, out=f)

    # ── تلوين الظلال/الإضاءة بألوان النوع (في المكان · قنوات على حدة) ──
    if palette:
        try:
            cols = [(int(str(c).lstrip("#")[i2:i2 + 2], 16) / 255.0) for c in palette[:3]
                    for i2 in (0, 2, 4)]
            sh = np.array(cols[0:3], np.float32)
            hi = np.array(cols[-3:], np.float32)
            lum = b["lum"]
            np.multiply(f, np.array([0.299, 0.587, 0.114], np.float32), out=t)
            np.sum(t, axis=2, out=lum)
            shm, him = t[:, :, 0], t[:, :, 1]            # إعادة استخدام أول قناتين كمساحات
            np.multiply(lum, -1.8, out=shm)
            shm += 1.0
            np.clip(shm, 0, 1, out=shm)
            np.multiply(shm, 0.14 * (sh[0] - 0.5), out=shm)
            f[:, :, 0] += shm
            np.multiply(lum, -1.8, out=shm)
            shm += 1.0
            np.clip(shm, 0, 1, out=shm)
            np.multiply(shm, 0.14 * (sh[1] - 0.5), out=shm)
            f[:, :, 1] += shm
            np.multiply(lum, -1.8, out=shm)
            shm += 1.0
            np.clip(shm, 0, 1, out=shm)
            np.multiply(shm, 0.14 * (sh[2] - 0.5), out=shm)
            f[:, :, 2] += shm
            np.multiply(lum, 1.8, out=him)
            him -= 0.8
            np.clip(him, 0, 1, out=him)
            np.multiply(him, 0.10 * (hi[2] - 0.5), out=him)
            f[:, :, 2] += him
            np.clip(f, 0, 1, out=f)
        except Exception:
            pass

    # ── بلوم ناعم من نسخة مصغّرة (رخيص في الرام والوقت) ──
    try:
        small = Image.fromarray(np.clip(f * 255.0, 0, 255).astype(np.uint8)).resize(
            (max(2, w // 8), max(2, h // 8)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(2.2))
        up = small.resize((w, h), Image.BILINEAR)
        if up.size != (w, h):
            up = up.resize((w, h), Image.BILINEAR)
        np.multiply(np.asarray(up, np.float32), 1.0 / 255.0 * (0.10 if calm else 0.16), out=t)
        np.add(f, t, out=f)
    except Exception:
        pass

    if n_p:                                              # جزيئات (عمق بصري)
        ys = (py + (i * pv * 1.4)).astype(int) % h
        xs = (px + (np.sin(i / 60.0 + px % 7) * 5)).astype(int) % w
        np.add(f[ys, xs], 0.13, out=f[ys, xs])

    try:
        breath = 1.0 + 0.018 * math.sin(2 * math.pi * i / (30.0 * 7.0))
        f *= breath
        np.multiply(f, grade.vig_mask(h, w, 0.24, 1.5)[:, :, None], out=f)   # فينييت (مخزن جاهز)
        from engine.photo import leak_tile                 # بلاطة صغيرة ⇒ تكبير في المخزن
        _lt = leak_tile(w, h, i, max(1, body), 0.14)
        _lg = Image.fromarray((np.clip(_lt, 0, 1) * 255).astype(np.uint8)).resize((w, h),
                                                                                 Image.BILINEAR)
        np.multiply(np.asarray(_lg, np.float32), 1.0 / 255.0, out=t)
        np.add(f, t, out=f)
        np.multiply(grade.grain_tiles(h, w)[i % 8], (0.004 if calm else 0.007), out=t)
        f += t
        np.clip(f, 0, 1, out=f)
    except Exception:
        np.clip(f, 0, 1, out=f)
    return f


def render_reel(paths: list[pathlib.Path], out_path, seconds: float, w: int = 720, h: int = 1280,
                fps: int = 30, palette=None, look: str = "cinema_cool", seed: int = 7,
                texts: list | None = None, crf: int = 21, calm: bool = False,
                loop_back: bool | None = None, seg_seconds: float | None = None,
                maxrate: str | None = None, stickers: list | None = None,
                progress: bool = True, watermark: str | None = "@xDaw_NoVa",
                hook: str | None = None) -> pathlib.Path:
    """يرندر الشورت من **مقاطع فيديو حقيقية**: قصّ سينمائي + تلاشي متبادل + هوية بصرية + نص.

    - كل مقطع بياخد حركة كاميرا مختلفة (تقريب/انزياح/تحريك) على نافذة متحركة.
    - تلاشي متبادل ناعم بين كل مقطعين، والمقاطع بتتكرر لو المدة أطول.
    - آخر ~٠.٩ ثانية بترجع لأول كادر (لوب ناعم لإعادة التشغيل).
    """
    from collections import deque

    from engine.editor import _draw_text
    from engine.photo import _mix

    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    total = int(round(seconds * fps))
    paths = [pathlib.Path(p) for p in paths if pathlib.Path(p).exists()]
    if not paths:
        raise RuntimeError("مفيش مقاطع فيديو صالحة")
    rng.shuffle(paths)
    n = len(paths)

    if loop_back is None:
        loop_back = not calm
    back = max(4, int(0.9 * fps)) if (loop_back and not calm and total > 10 * fps) else 0
    body = total - back
    over = 1.06 if calm else 1.14                      # الطويلة: هامش أقل = ديكود أخف
    W, H = int(w * over) // 2 * 2, int(h * over) // 2 * 2
    seg = max(1.2, min(seg_seconds or (body / float(fps) / max(2, n)), 7.0))
    per = max(int(fps), int(round(seg * fps)))
    trans = max(4, min(int(per * (0.08 if calm else 0.16)), int((0.35 if calm else 0.7) * fps)))

    cmd = [proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-g", str(fps * 2)]
    if maxrate:                                   # 🧯 سقف البتريت (الطويلة ما تكبرش أوي)
        _buf = str(maxrate).rstrip("kK") + "k"
        cmd += ["-maxrate", str(maxrate), "-bufsize", _buf]
    cmd += ["-movflags", "+faststart", str(out_path)]
    _errlog = pathlib.Path(tempfile.gettempdir()) / "dollars_clips_ffmpeg.log"
    _errf = open(_errlog, "wb")
    pipe = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=_errf)

    rg = np.random.default_rng(seed)
    n_p = 70 if calm else 190
    px, py = rg.integers(0, w, n_p), rg.integers(0, h, n_p)
    pv = rg.uniform(0.2, 0.9, n_p)

    st = {"i": 0, "first": None}
    # ⚠️ الذاكرة: بنخزّن كادرات التلاشي واللوب كـ uint8 (٨× أصغر من float32) — الرام محدودة
    tailbuf: deque = deque(maxlen=max(1, back))       # آخر كادرات (للوب) — uint8
    ring: deque = deque(maxlen=trans)                 # كادرات التلاشي — uint8

    def _write(fr01: np.ndarray):
        i = st["i"]
        t_now = i / float(fps)
        if fr01.dtype == np.uint8:
            fr = fr01                                  # جاهز
        else:                                          # تحويل بلا نسخ زايدة
            _t = _bufs(fr01.shape[0], fr01.shape[1])["t"]
            np.multiply(fr01, 255.0, out=_t)
            np.clip(_t, 0, 255, out=_t)
            fr = _t.astype(np.uint8)
        if texts:
            for tx in texts:
                if float(tx.get("at", 0)) <= t_now < float(tx.get("at", 0)) + float(tx.get("dur", 3)):
                    if tx.get("card"):
                        from engine import overlays as _ov
                        fr = _ov.caption_card(fr, str(tx.get("text", "")), t_now,
                                              float(tx.get("at", 0)), float(tx.get("dur", 3)),
                                              size=float(tx.get("size", 0.052)),
                                              y=float(tx.get("y", 0.76)))
                    else:
                        fr = _draw_text(fr, str(tx.get("text", "")), pos=tx.get("pos", "lower"),
                                        size=float(tx.get("size", 0.055)))
                    break
        # ✨ إضافات المونتاج (ملصقات · شريط تقدّم · هوك · علامة القناة)
        if hook or stickers or watermark:
            from engine import overlays as _ov
            if hook and t_now < 3.2:
                fr = _ov.hook_badge(fr, hook, t_now, dur=3.2)
            for sk in (stickers or []):
                if float(sk["at"]) <= t_now < float(sk["at"]) + float(sk["dur"]):
                    fr = _ov.draw_sticker(fr, sk["code"], t_now, float(sk["at"]), float(sk["dur"]),
                                          x=float(sk.get("x", 0.78)), y=float(sk.get("y", 0.28)),
                                          size=float(sk.get("size", 0.14)))
            if watermark:
                fr = _ov.watermark(fr, watermark)
            if progress:
                fr = _ov.progress_bar(fr, t_now / max(0.1, body / float(fps)))
        arr = np.ascontiguousarray(fr)
        if i < body:
            pipe.stdin.write(memoryview(arr))
        if back:
            tailbuf.append(arr)
        st["i"] = i + 1
        return arr

    def _style(fr: np.ndarray) -> np.ndarray:
        return _look(fr.astype(np.float32) / 255.0, st["i"], palette, look, n_p,
                     px, py, pv, h, w, body, calm)

    last = None
    try:
        done = False
        for _pass in range(4):                        # لو المقاطع قصيرة، بنلف عليهم تاني
            if done:
                break
            for p in paths:
                if st["i"] >= body:
                    done = True
                    break
                _, _, csecs = probe(p)
                need = per / float(fps)
                start = 0.0
                if csecs and csecs > need + 0.6:
                    start = rng.uniform(0.0, min(csecs - need - 0.3, csecs * 0.6))
                mode = rng.choice(["in", "out", "pan", "drift"])
                snap = list(ring)                          # مرجع فقط (مش نسخة بيانات)
                k = 0
                for fr in _decode(p, W, H, fps, need, start):
                    if st["i"] >= body or k >= per:
                        break
                    u = min(1.0, k / float(max(1, per - 1)))
                    if mode == "in":
                        sc, dx, dy = over - 0.10 * u, 0.0, 0.03 * (u - 0.5)
                    elif mode == "out":
                        sc, dx, dy = 1.06 + 0.08 * u, 0.0, -0.03 * (u - 0.5)
                    elif mode == "pan":
                        sc, dx, dy = 1.08, (0.7 - 1.4 * u), 0.0
                    else:
                        sc, dx, dy = 1.10, 0.35 * math.sin(u * 3.1), 0.3 * math.cos(u * 2.2)
                    styled = _style(_window(fr, w, h, sc, dx, dy))
                    if k < trans and len(snap) == trans:      # 🔀 تلاشي مع المقطع السابق
                        a_t = ((k + 1) / float(trans)) ** 1.3
                        styled = _mix(snap[k].astype(np.float32) / 255.0, styled, a_t)
                    arr = _write(styled)
                    if st["first"] is None:
                        st["first"] = arr[:]                  # uint8 (ذاكرة رخيصة)
                    ring.append(arr)                          # uint8 للتلاشي الجاي
                    last = arr
                    k += 1
                del snap
                import gc as _gc
                _gc.collect()                                 # نرجّع الذاكرة للمصنع فورًا

        while st["i"] < body:                          # شبكة أمان (نادرًا)
            base = last if last is not None else np.zeros((h, w, 3), np.uint8)
            _write(base.astype(np.float32) / 255.0 if base.dtype != np.uint8 else base)

        if back:                                       # 🔁 رجوع سلس لأول كادر
            first = st["first"] if st["first"] is not None else np.zeros((h, w, 3), np.uint8)
            firstf = first.astype(np.float32) / 255.0
            frames = list(tailbuf)[-back:] or [first]
            _span = max(1.0, back * 0.38)          # نكمل الرجوع بسرعة وبعدها نثبت على أول كادر
            for j in range(back):
                a = min(1.0, (j + 1) / _span)
                a = a * a * (3.0 - 2.0 * a)
                base = frames[min(j, len(frames) - 1)].astype(np.float32) / 255.0
                out = np.clip(base * (1.0 - a) + firstf * a, 0, 1)
                pipe.stdin.write(memoryview(np.ascontiguousarray((out * 255).astype(np.uint8))))
                del base, out
    finally:
        try:
            pipe.stdin.close()
        except Exception:
            pass
        rc = pipe.wait()
        try:
            _errf.close()
        except Exception:
            pass
        err = _errlog.read_text(encoding="utf-8", errors="ignore") if _errlog.exists() else ""
    if rc != 0:
        raise RuntimeError(f"ffmpeg فشل: {err[:300]}")
    return out_path
