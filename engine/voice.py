#!/usr/bin/env python3
"""
🗣️ محرّك الصوت البشري — Dollars Studio
=====================================
فيديوهاتنا بقت **بتتكلم**: تعليق صوتي حقيقي بنطق سليم، بلا مفتاح وبلا فلوس.

المسارات (بالترتيب — وأول واحد ينجح يكفي):
    1) edge-tts   → أصوات نيون من مايكروسوفت (ar-EG · ar-SA · en-US · …) جودة عالية جدًا
    2) gTTS       → احتياطي (جوجل) لو الأول وقع
    3) مفيش صوت   → الفيديو ينزل عادي (المصنع مايتوقفش أبدًا)

الاستخدام:
    from engine import voice
    segs = [{"text": "خد نفس عميق… واتركه", "at": 1.2}]
    files = voice.narrate(segs, lang="ar", workdir="/var/tmp/x")   # [{at, path, dur}]
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ── الأصوات: كذا صوت لكل لغة (رجالي/نسائي) عشان القناة تبان بشرية مش روبوت واحد ──
VOICES: dict[str, list[tuple[str, str]]] = {
    "ar": [("ar-EG-ShakirNeural", "m"), ("ar-EG-SalmaNeural", "f"),
           ("ar-SA-HamedNeural", "m"), ("ar-SA-ZariyahNeural", "f")],
    "en": [("en-US-AndrewNeural", "m"), ("en-US-AriaNeural", "f"),
           ("en-GB-RyanNeural", "m"), ("en-US-EmmaNeural", "f")],
    "es": [("es-ES-AlvaroNeural", "m"), ("es-MX-DaliaNeural", "f")],
    "pt": [("pt-BR-AntonioNeural", "m"), ("pt-BR-FranciscaNeural", "f")],
    "hi": [("hi-IN-MadhurNeural", "m"), ("hi-IN-SwaraNeural", "f")],
    "id": [("id-ID-ArdiNeural", "m"), ("id-ID-GadisNeural", "f")],
    "fr": [("fr-FR-HenriNeural", "m"), ("fr-FR-DeniseNeural", "f")],
    "de": [("de-DE-ConradNeural", "m"), ("de-DE-KatjaNeural", "f")],
    "ru": [("ru-RU-DmitryNeural", "m"), ("ru-RU-SvetlanaNeural", "f")],
    "tr": [("tr-TR-AhmetNeural", "m"), ("tr-TR-EmelNeural", "f")],
    "ja": [("ja-JP-KeitaNeural", "m"), ("ja-JP-NanamiNeural", "f")],
    "ko": [("ko-KR-InJoonNeural", "m"), ("ko-KR-SunHiNeural", "f")],
    "it": [("it-IT-DiegoNeural", "m"), ("it-IT-ElsaNeural", "f")],
}

# أرقام → كلمات (النطق الصح: «٤٥» تتقال «خمسة وأربعين» مش «أربعة خمسة»)
EN_NUM = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
          8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
          14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen",
          19: "nineteen", 20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty",
          70: "seventy", 80: "eighty", 90: "ninety"}
AR_NUM = {"0": "صفر", "1": "واحد", "2": "اتنين", "3": "تلاتة", "4": "أربعة", "5": "خمسة", "6": "ستة",
          "7": "سبعة", "8": "تمانية", "9": "تسعة", "10": "عشرة", "11": "حداشر", "12": "اتناشر",
          "15": "خمستاشر", "20": "عشرين", "30": "تلاتين", "40": "أربعين", "45": "خمسة وأربعين",
          "50": "خمسين", "60": "ستين", "90": "تسعين", "100": "مية", "1000": "ألف"}
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d]+")
HASHTAG = re.compile(r"#[\w\u0600-\u06FF]+")


def _num_to_words_en(n: int) -> str:
    if n in EN_NUM:
        return EN_NUM[n]
    if 20 < n < 100:
        t, o = divmod(n, 10)
        return f"{EN_NUM[t*10]}-{EN_NUM[o]}"
    if 100 <= n < 1000:
        h, r = divmod(n, 100)
        return f"{EN_NUM[h]} hundred" + (f" {_num_to_words_en(r)}" if r else "")
    return str(n)


def normalize(text: str, lang: str = "en") -> str:
    """ينضّف النص للنُطق الصح: يشيل الهاشتاجات والرموز، ويحوّل الأرقام لكلمات."""
    t = (text or "").replace("…", "..")
    t = EMOJI.sub(" ", t)
    t = HASHTAG.sub(" ", t)
    t = t.replace("🔎", " ").replace("·", ",").replace("|", ",").replace("—", ",").replace("–", ",")
    t = re.sub(r"[*_`~^<>\[\]{}]", " ", t)
    t = re.sub(r"[•●▪️✨🎬🎧🪝📌👁️❤️💬]", " ", t)
    # أرقام → كلمات (نطق سليم)
    def _rep(m):
        raw = m.group(0)
        try:
            n = int(raw)
        except Exception:
            return raw
        if lang.startswith("ar") and raw in AR_NUM:
            return AR_NUM[raw]
        return _num_to_words_en(n) if lang.startswith("en") else raw
    t = re.sub(r"\b\d{1,4}\b", _rep, t)
    # وحدات شائعة
    t = re.sub(r"\b(\d+h|\d+\s?h)\b", " hours", t, flags=re.I)
    t = re.sub(r"\b(\d+s)\b", " seconds", t, flags=re.I)
    t = re.sub(r"\bsec\b", "second", t, flags=re.I)
    t = re.sub(r"\bASMR\b", "A S M R", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,.")
    if not t:
        return ""
    return t if t[-1] in ".!?؟" else t + "."


def _cache_dir() -> pathlib.Path:
    base = (os.environ.get("DOLLARS_VOICE_CACHE") or "").strip()
    d = pathlib.Path(base) if base else (ROOT / "state" / "voice_cache")
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        d = pathlib.Path("/tmp/voice_cache")
        d.mkdir(parents=True, exist_ok=True)
    return d


def _ff() -> str:
    try:
        from engine import proc
        return proc.FFMPEG
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _duration(path) -> float:
    try:
        r = subprocess.run([_ff(), "-i", str(path)], capture_output=True, text=True, timeout=60)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", (r.stderr or ""))
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        pass
    return 0.0


def _pick_voice(lang: str, seed: int = 0) -> str:
    pool = VOICES.get(lang[:2].lower()) or VOICES["en"]
    return pool[abs(int(seed)) % len(pool)][0]


def say(text: str, lang: str = "en", out: pathlib.Path | str | None = None, voice: str | None = None,
        rate: str = "-4%", seed: int = 0) -> pathlib.Path | None:
    """ينطق جملة واحدة ويرجّع ملف الصوت (mp3/wav) — أو None لو كل المسارات فشلت.

    النطق السليم: النص بيتنضّف الأول (أرقام كلمات · شيل رموز/هاشتاجات) وبعدين بيتقال.
    """
    clean = normalize(text, lang)
    if not clean or len(clean) < 2:
        return None
    v = voice or _pick_voice(lang, seed)
    key = hashlib.sha1(f"{clean}|{v}|{rate}".encode("utf-8")).hexdigest()[:20]
    cdir = _cache_dir()
    cached = cdir / f"{key}.mp3"
    if cached.exists() and cached.stat().st_size > 1500:
        if out:
            shutil.copy(cached, out)
            return pathlib.Path(out)
        return cached
    target = pathlib.Path(out) if out else cached

    # 1) edge-tts (أحسن جودة)
    try:
        import asyncio
        import edge_tts

        async def _go():
            c = edge_tts.Communicate(clean, v, rate=rate)
            await c.save(str(target))
        asyncio.run(asyncio.wait_for(_go(), timeout=90))
        if target.exists() and target.stat().st_size > 1500:
            if target != cached:
                try:
                    shutil.copy(target, cached)
                except Exception:
                    pass
            return target
    except Exception as e:
        if os.environ.get("DOLLARS_DEBUG"):
            print(f"   🗣️ edge-tts اتعذّر ({type(e).__name__}) — بجرّب الاحتياطي", flush=True)

    # 2) gTTS احتياطي
    try:
        from gtts import gTTS
        gTTS(text=clean, lang=lang[:2], slow=False).save(str(target))
        if target.exists() and target.stat().st_size > 1500:
            return target
    except Exception:
        pass
    return None


def narrate(segments: list[dict], lang: str = "en", workdir=None, voice: str | None = None,
            rate: str = "-4%", seed: int = 0, max_seconds: float | None = None) -> list[dict]:
    """ينطق مجموعة جمل ويرجّع [{at, path, dur, text}] جاهزة للمونتاج.

    كل جملة بتتنطق لوحدها عشان تتزامن مع الكلام المكتوب على الشاشة في نفس اللحظة.
    """
    wd = pathlib.Path(workdir or (_cache_dir() / "seg"))
    wd.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    for i, seg in enumerate(segments or []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        p = say(text, lang=lang, out=wd / f"seg{i:02d}.mp3", voice=voice, rate=rate, seed=seed + i)
        if not p:
            continue
        d = _duration(p)
        if d <= 0.2:
            continue
        out.append({"at": float(seg.get("at") or 0.0), "path": str(p), "dur": round(d, 3), "text": text})
    # ⏱️ لو المقطع أطول من الفيديو: نقصّ الآخر (بنسيب المتاح بالترتيب)
    if max_seconds:
        out = [s for s in out if s["at"] < max_seconds - 0.6]
    return out


def to_wav(src, dst, sr: int = 44100) -> str | None:
    """يحوّل أي ملف صوت لـwav ستيريو موحّد (للمونتاج مع باقي المسارات)."""
    try:
        subprocess.run([_ff(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
                        "-ac", "2", "-ar", str(sr), "-c:a", "pcm_s16le", str(dst)],
                       check=True, timeout=180)
        return str(dst)
    except Exception:
        return None


if __name__ == "__main__":      # تجربة سريعة: نطق عربي وإنجليزي
    import sys as _s
    _txt = " ".join(_s.argv[1:]) or "استرخِ معنا لحظة. خد نفس عميق، واتركه بهدوء."
    print("نص بعد التنضيف:", normalize(_txt, "ar"))
    p = say(_txt, lang="ar", out="/tmp/voice_test.mp3", seed=0)
    print("الملف:", p, "| المدة:", round(_duration(p), 2) if p else "—")
