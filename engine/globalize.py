"""🌍 تعريب/دبلجة عالمية — Dollars Studio

الفيديوهات بتطلع إنجليزي (الأساسي)، والوحدة دي بتخليها **لعالم كله**:

    • عناوين ووصف بلغات كتير (localizations الرسمية في يوتيوب API)
    • ملفات ترجمة (SRT) بلغات كتير على الفيديو — ويوتيوب يكمّل الباقي تلقائيًا
    • اختيار اللغات حسب البلاد اللي بتشوف القناة أكتر (بنسجّلها في state)

الترجمة بتحصل بمفتاح LLM (LLM_API_KEY / GROQ_API_KEY). لو مفيش مفتاح:
كل حاجة تشتغل عادي من غير ترجمة (المصنع مايتوقفش أبدًا).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 🌍 لغات الأساس (الأكثر مشاهدة عالميًا) + العربي ضمنهم
LANGS_DEFAULT = ["ar", "es", "pt", "hi", "id", "fr", "de", "ru", "tr", "ja", "ko", "it"]
LANG_NAMES = {"ar": "Arabic", "es": "Spanish", "pt": "Portuguese", "hi": "Hindi", "id": "Indonesian",
              "fr": "French", "de": "German", "ru": "Russian", "tr": "Turkish", "ja": "Japanese",
              "ko": "Korean", "it": "Italian", "en": "English"}


def llm_key() -> str | None:
    return (os.environ.get("LLM_API_KEY") or os.environ.get("GROQ_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY") or None)


def _llm(prompt: str, timeout: int = 40) -> str | None:
    """نداء LLM مختصر (Groq/OpenAI-compatible). بيرجّع نص أو None لو مفيش مفتاح."""
    key = llm_key()
    if not key:
        return None
    base = os.environ.get("LLM_API_BASE") or ("https://api.groq.com/openai/v1" if os.environ.get("GROQ_API_KEY")
                                             else "https://api.openai.com/v1")
    model = os.environ.get("LLM_MODEL") or ("llama-3.1-8b-instant" if "groq" in base else "gpt-4o-mini")
    body = json.dumps({"model": model, "temperature": 0.2, "max_tokens": 900,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(f"{base}/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        return (d["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return None


def _gtx(text: str, lang: str, timeout: int = 25) -> str | None:
    """🌐 ترجمة حقيقية **بلا أي مفتاح** (نقطة جوجل العامة client=gtx).

    دي اللي بتخلي النسخة العربية الأساسية والترجمات العالمية تشتغل في السحابة
    من غير ما نستنى مفتاح LLM — صفر تكلفة، وشغّالة على النصوص القصيرة (عنوان/وصف).
    """
    text = (text or "").strip()
    if not text:
        return None
    out = []
    for i in range(0, len(text), 1200):                       # نقطع عند ~١٢٠٠ حرف
        part = text[i:i + 1200]
        q = urllib.parse.quote(part)
        url = (f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl={lang}"
               f"&dt=t&q={q}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Dollars/1.0)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            seg = "".join(s[0] for s in (data[0] or []) if s and s[0])
            out.append(seg)
        except Exception:
            return None
    got = "".join(out).strip()
    return got or None


_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]")


def _keep_tail(src: str, dst: str) -> str:
    """نحافظ على الهاشتاجات والإيموجي الأصلية بعد الترجمة (مهمة للخوارزمية).

    أي هاشتاج مترجم (زي #شورت) بيتشال، والهاشتاج الأصلي بيرجع زي ما هو.
    """
    src_tags = re.findall(r"#[\w\u0600-\u06FF]+", src)
    def _sub(m):
        return m.group(0) if m.group(0) in src_tags else " "
    dst2 = re.sub(r"#[\w\u0600-\u06FF]+", _sub, dst)
    miss = [t for t in _EMOJI_RE.findall(src) if t not in dst2] + [t for t in src_tags if t not in dst2]
    return re.sub(r"[ \t]{2,}", " ", (dst2 + " " + " ".join(miss)).strip()).strip()


def translate_fields(title: str, description: str, langs: list[str] | None = None) -> dict:
    """ترجمة العنوان والوصف لعدة لغات. بيرجّع {lang: {"title":…, "description":…}}.

    المسار الأول: LLM (لو فيه مفتاح). المسار الثاني: ترجمة مجانية بلا مفتاح (_gtx)
    فأي لغة ناقصة بتتكمّل — عشان الفيديو يفضل «لكل العالم» في كل الحالات.
    """
    langs = [x for x in (langs or LANGS_DEFAULT) if x != "en"]
    if not langs or not title:
        return {}
    out: dict[str, dict] = {}
    # كل نداء بياخد مجموعة لغات — أقل تكلفة وأسرع
    if not llm_key():
        return _gtx_fields(title, description, langs)
    for i in range(0, len(langs), 6):
        chunk = langs[i:i + 6]
        names = ", ".join(f"{c}={LANG_NAMES.get(c, c)}" for c in chunk)
        prompt = ("Translate the YouTube title and description below into these languages. "
                  "Keep hashtags and emojis. Keep the same tone, short and clickable, no extra notes.\n"
                  f"Languages: {names}\n"
                  'Reply ONLY with JSON: {"<code>": {"title": "...", "description": "..."}, ...}\n\n'
                  f"TITLE: {title}\n\nDESCRIPTION:\n{description[:1200]}")
        raw = _llm(prompt)
        if not raw:
            continue
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
        try:
            got = json.loads(raw)
        except Exception:
            continue
        for code, val in (got or {}).items():
            if code in chunk and isinstance(val, dict) and val.get("title"):
                out[code] = {"title": str(val["title"])[:100],
                             "description": str(val.get("description") or "")[:4900]}
    missing = [c for c in langs if c not in out]                 # اللي الـLLM سابه نكمّله مجانًا
    if missing:
        out.update(_gtx_fields(title, description, missing))
    return out


def _gtx_fields(title: str, description: str, langs: list[str]) -> dict:
    """نسخة «بلا مفتاح» من الترجمة — لكل اللغات المطلوبة."""
    out: dict[str, dict] = {}
    for code in langs:
        t = _gtx(title, code)
        if not t:
            continue
        d = _gtx(description, code) if description else None
        out[code] = {"title": _keep_tail(title, t)[:100],
                     "description": ((_keep_tail(description, d) if d else description) or "")[:4900]}
    return out


def translate_srt(srt: str, langs: list[str] | None = None, limit_lines: int = 40) -> dict:
    """ترجمة ملف ترجمة لعدة لغات (سطر سطر مع الحفاظ على التوقيتات)."""
    langs = [x for x in (langs or LANGS_DEFAULT[:6]) if x != "en"]
    if not srt or not langs:
        return {}
    lines = [ln.strip() for ln in srt.replace("\r\n", "\n").split("\n")]
    text_idx = [i for i, ln in enumerate(lines) if ln and not ln.isdigit() and "-->" not in ln][:limit_lines]
    if not text_idx:
        return {}
    texts = [lines[i] for i in text_idx]
    out: dict[str, str] = {}
    for code in langs:
        prompt = ("Translate each line to " + LANG_NAMES.get(code, code) +
                  ". Keep it short and natural for subtitles. "
                  'Reply ONLY JSON: {"lines": ["...", "..."]} with the same order and count.\n\n'
                  + json.dumps(texts, ensure_ascii=False))
        raw = _llm(prompt)
        if not raw:
            continue
        raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
        try:
            got = json.loads(raw).get("lines") or []
        except Exception:
            continue
        if len(got) != len(texts):
            continue
        new = list(lines)
        for pos, idx in enumerate(text_idx):
            new[idx] = str(got[pos])
        out[code] = "\r\n".join(new) + "\r\n"
    return out


def apply_localizations(video_id: str, title: str, description: str, token: str,
                        langs: list[str] | None = None) -> int:
    """يحط العناوين/الأوصاف المترجمة على الفيديو (يوتيوب يعرضها للناس بلغتهم)."""
    tr = translate_fields(title, description, langs=langs)
    if not tr:
        return 0
    q = "https://www.googleapis.com/youtube/v3/videos?part=localizations"
    body = json.dumps({"id": video_id, "localizations": tr}).encode()
    req = urllib.request.Request(q, data=body, method="PUT",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            ok = r.status == 200
        return len(tr) if ok else 0
    except Exception:
        return 0


def globalize_video(video_id: str, title: str, description: str, token: str, srt: str | None = None,
                    langs: list[str] | None = None) -> dict:
    """كل حاجة مرة واحدة: عناوين/أوصاف عالمية + ملفات ترجمة بلغات كتير."""
    res = {"localized": 0, "captions": 0}
    res["localized"] = apply_localizations(video_id, title, description, token, langs=langs)
    if srt:
        from engine import publish as _pb
        caps = translate_srt(srt, langs=[x for x in (langs or LANGS_DEFAULT[:6])])
        for code, text in caps.items():
            try:
                if _pb.upload_captions(video_id, text, language=code,
                                       name=f"{LANG_NAMES.get(code, code)} (auto)", token=token):
                    res["captions"] += 1
            except Exception:
                continue
    return res


if __name__ == "__main__":                     # فحص سريع بدون يوتيوب
    print("مفتاح LLM موجود:", bool(llm_key()))
    if llm_key():
        print(json.dumps(translate_fields("Ocean waves at sunset #shorts",
                                          "Relaxing ocean waves. #shorts", ["ar", "es"]),
                         ensure_ascii=False)[:400])
