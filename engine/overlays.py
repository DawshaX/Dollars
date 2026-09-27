"""
✨ طبقة الإضافات فوق الفيديو — ملصقات متحركة · شريط تقدّم · كابشنات فاخرة · علامة القناة
=========================================================================================
بتحوّل الشورت من «مقطع + نص» لشغل مونتاج حقيقي:
    • ملصقات إيموجي (Twemoji — رخصة CC-BY 4.0) بتظهر بأنيميشن نطة (pop-in) وتختفي بنعومة
    • شريط تقدّم رفيع فوق (إحساس «السلسلة/الستوري» اللي الناس متعودة عليه)
    • كابشنات على كارت نص شفاف (أوضح بكتير من النص العائم)
    • بادج للهوك في الأول + علامة القناة (watermark) خفيفة
كل حاجة **مرسومة بالكود** على الكادر (بلا مكتبات خارجية تقيلة).
"""
from __future__ import annotations

import math
import os
import pathlib
import re
import tempfile
import urllib.request

import numpy as np
from PIL import Image, ImageDraw

from engine.editor import _font

STICKER_DIR = pathlib.Path(os.environ.get("DOLLARS_STICKER_CACHE") or
                           (pathlib.Path(tempfile.gettempdir()) / "dollars_stickers"))
UA = {"User-Agent": "DollarsStudio/1.0 (+https://github.com/DawshaX/Dollars)"}

# 🎨 ملصقات بلغة الإيموجي — كل نوع بياخد ملصقات بتناسب إحساسه
EMOJI = {
    "fire": "1f525", "sparkles": "2728", "star": "2b50", "heart": "2764-fe0f",
    "laugh": "1f602", "eyes": "1f440", "brain": "1f9e0", "bulb": "1f4a1",
    "moon": "1f319", "zzz": "1f4a4", "headphones": "1f3a7", "wave": "1f30a",
    "coffee": "2615", "rain": "1f327-fe0f", "clock": "23f0", "leaf": "1f343",
    "camera": "1f3a5", "music": "1f3b5", "rocket": "1f680", "earth": "1f30d",
    "money": "1f4b0", "thumbs": "1f44d", "clap": "1f44f", "wow": "1f62e",
    "snow": "2744-fe0f", "sun": "2600-fe0f", "candle": "1f56f-fe0f", "tea": "1f375",
}

# خريطة النوع → ملصقات مناسبة (بترتيب الاستخدام)
GENRE_STICKERS = {
    "sleep_ambience": ["moon", "zzz", "wave", "leaf"],
    "focus_study": ["brain", "clock", "coffee", "headphones"],
    "satisfying": ["sparkles", "star", "wow", "thumbs"],
    "facts": ["bulb", "brain", "wow", "star"],
    "space_nature": ["rocket", "earth", "star", "sparkles"],
    "fun_memes": ["laugh", "fire", "eyes", "wow"],
    "story": ["heart", "star", "moon", "sparkles"],
    "calm_wellness": ["leaf", "heart", "sparkles", "tea"],
    "asmr": ["headphones", "wave", "sparkles", "rain"],
    "comfort_relax": ["coffee", "tea", "heart", "leaf"],
    "funny": ["laugh", "fire", "thumbs", "clap"],
    "rain_nature": ["rain", "leaf", "wave", "coffee"],
}

# التوثيق (شرط رخصة Twemoji)
EMOJI_CREDIT = "Emoji graphics: Twemoji (CC-BY 4.0) — https://github.com/jdecked/twemoji"


def sticker(code: str) -> Image.Image | None:
    """يجيب ملصق إيموجي (PNG شفاف) — مخزّن مرّة واحدة. لا شبكة؟ بنرجع None بهدوء."""
    code = str(code).lower()
    if code in EMOJI:
        code = EMOJI[code]
    STICKER_DIR.mkdir(parents=True, exist_ok=True)
    p = STICKER_DIR / f"{code}.png"
    if not p.exists():
        for url in (f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/72x72/{code}.png",
                    f"https://raw.githubusercontent.com/jdecked/twemoji/main/assets/72x72/{code}.png"):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                    raw = r.read()
                if len(raw) > 300:
                    p.write_bytes(raw)
                    break
            except Exception:
                continue
    if not p.exists():
        return None
    try:
        return Image.open(p).convert("RGBA")
    except Exception:
        return None


def _ease_out_back(u: float) -> float:
    """نطة ناعمة (overshoot) للظهور — إحساس أنيميشن احترافي."""
    u = max(0.0, min(1.0, u))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


_SCREEN_OK = set(chr(c) for c in range(0x20, 0x7F)) | set("’‘“”…—–•·")


def on_screen(text: str, limit: int | None = None) -> str:
    """نص صالح للعرض على الشاشة (لاتيني) — العربي من غير تشكيل بيطلع مشوّه على الفيديو."""
    t = (text or "").strip()
    if not t or any(ch not in _SCREEN_OK for ch in t):
        return ""
    return t[:limit] if limit else t


def draw_sticker(frame: np.ndarray, code: str, t: float, at: float, dur: float,
                 x: float = 0.78, y: float = 0.28, size: float = 0.15,
                 rotate: float = 0.0) -> np.ndarray:
    """يرسم ملصق بأنيميشن: ظهور بنطة → ثبات مع دوران خفيف → اختفاء بتلاشي."""
    if not (at <= t < at + dur):
        return frame
    img = sticker(code)
    if img is None:
        return frame
    u = (t - at) / max(0.001, dur)
    pop, fade = 0.34, 0.45                     # ثواني الظهور والاختفاء
    if u * dur < pop:
        k = _ease_out_back((u * dur) / pop)
    elif (1 - u) * dur < fade:
        k = max(0.0, ((1 - u) * dur) / fade)
    else:
        k = 1.0
    if k <= 0.02:
        return frame
    H, W = frame.shape[:2]
    side = max(12, int(H * size * min(1.0, 0.55 + 0.45 * k)))
    im = img.resize((side, side), Image.LANCZOS)
    if rotate or True:                         # ميل خفيف ثابت يعطي حياة
        im = im.rotate(-6 if int(t * 2) % 2 == 0 else 5, resample=Image.BICUBIC, expand=True)
    if k < 0.98:                               # تلاشي الاختفاء
        a = im.split()[3].point(lambda v: int(v * min(1.0, k / 0.98)))
        im.putalpha(a)
    base = Image.fromarray(frame).convert("RGBA")
    px = int(np.clip(x * W - im.width / 2, 0, W - im.width))
    py = int(np.clip(y * H - im.height / 2, 0, H - im.height))
    base.alpha_composite(im, (px, py))
    return np.asarray(base.convert("RGB"), dtype=np.uint8)


def progress_bar(frame: np.ndarray, frac: float, color=(255, 255, 255), thickness: int = 5,
                 alpha: int = 190) -> np.ndarray:
    """شريط تقدّم رفيع فوق — إحساس الستوري/السلسلة (بيرفع الإحساس بالجودة)."""
    H, W = frame.shape[:2]
    frac = float(np.clip(frac, 0, 1))
    th = max(2, thickness)
    ov = Image.new("RGBA", (W, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rectangle([0, 0, W, th], fill=(0, 0, 0, 70))
    d.rectangle([0, 0, max(2, int(W * frac)), th], fill=(color[0], color[1], color[2], alpha))
    base = Image.fromarray(frame).convert("RGBA")
    base.alpha_composite(ov, (0, 0))
    return np.asarray(base.convert("RGB"), dtype=np.uint8)


def caption_card(frame: np.ndarray, text: str, t_now: float, at: float, dur: float,
                 size: float = 0.052, y: float = 0.76, accent=(255, 255, 255)) -> np.ndarray:
    """كابشن على **كارت نص شفاف** مع ظهور/اختفاء ناعم — أوضح بكتير من النص العائم."""
    if not (at <= t_now < at + dur) or not str(text).strip():
        return frame
    H, W = frame.shape[:2]
    u = (t_now - at) / max(0.001, dur)
    a_in = min(1.0, (t_now - at) / 0.28)
    a_out = min(1.0, (at + dur - t_now) / 0.32)
    alpha = max(0.0, min(a_in, a_out))
    rise = int((1.0 - a_in) * H * 0.012)                  # صعود خفيف مع الظهور
    f = _font(max(16, int(H * size)))
    img = Image.fromarray(frame).convert("RGBA")
    d = ImageDraw.Draw(img)
    maxw = int(W * 0.84)
    words, lines, cur = str(text).split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if d.textlength(trial, font=f) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    lines = lines[:3]
    lh = int(f.size * 1.34)
    box_h = lh * len(lines) + int(H * 0.028)
    box_w = max(int(d.textlength(l, font=f)) for l in lines) + int(W * 0.075)
    box_w = min(box_w, int(W * 0.94))
    x0 = (W - box_w) // 2
    y0 = int(H * y) - box_h // 2 + rise
    y0 = max(int(H * 0.06), min(y0, H - box_h - int(H * 0.04)))
    pad = int(H * 0.012)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    do = ImageDraw.Draw(ov)
    do.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=pad * 2,
                         fill=(8, 10, 16, int(150 * alpha)))
    do.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=pad * 2,
                         outline=(accent[0], accent[1], accent[2], int(120 * alpha)), width=max(2, H // 540))
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img)
    ty = y0 + int(H * 0.012)
    for l in lines:
        tw = d.textlength(l, font=f)
        d.text(((W - tw) / 2, ty), l, font=f, fill=(255, 255, 255, int(255 * alpha)),
               stroke_width=max(1, H // 620), stroke_fill=(0, 0, 0, int(150 * alpha)))
        ty += lh
    return np.asarray(img.convert("RGB"), dtype=np.uint8)


def hook_badge(frame: np.ndarray, text: str, t_now: float, dur: float = 3.0,
               accent=(255, 90, 90)) -> np.ndarray:
    """بادج الهوك فوق (أول ثواني) — بيثبّت المشاهد قبل ما يسكرول."""
    if not str(text).strip() or t_now >= dur:
        return frame
    H, W = frame.shape[:2]
    alpha = max(0.0, min(1.0, (t_now) / 0.25, (dur - t_now) / 0.4))
    f = _font(max(16, int(H * 0.045)))
    img = Image.fromarray(frame).convert("RGBA")
    d = ImageDraw.Draw(img)
    txt = str(text).strip()[:42]
    tw = d.textlength(txt, font=f)
    bw, bh = int(tw + W * 0.10), int(f.size * 1.7)
    x0 = (W - bw) // 2
    y0 = int(H * 0.075)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    do = ImageDraw.Draw(ov)
    do.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=bh // 2,
                         fill=(accent[0], accent[1], accent[2], int(205 * alpha)))
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img)
    d.text(((W - tw) / 2, y0 + (bh - f.size) / 2 - H * 0.004), txt, font=f,
           fill=(255, 255, 255, int(255 * alpha)))
    return np.asarray(img.convert("RGB"), dtype=np.uint8)


def watermark(frame: np.ndarray, text: str = "@xDaw_NoVa") -> np.ndarray:
    """علامة القناة — خفيفة في الركن (بتبني هوية بدون ما تزعّج)."""
    if not text:
        return frame
    H, W = frame.shape[:2]
    f = _font(max(12, int(H * 0.026)))
    img = Image.fromarray(frame).convert("RGBA")
    d = ImageDraw.Draw(img)
    tw = d.textlength(text, font=f)
    x, y = W - tw - int(W * 0.045), H - int(H * 0.052)
    d.text((x, y), text, font=f, fill=(255, 255, 255, 165),
           stroke_width=1, stroke_fill=(0, 0, 0, 110))
    return np.asarray(img.convert("RGB"), dtype=np.uint8)


def plan_stickers(genre: str, seconds: float, seed: int = 0, count: int = 3) -> list[dict]:
    """يخطّط ظهور الملصقات على طول الفيديو (توقيتات وأماكن متنوعة)."""
    import random
    rng = random.Random(seed + 77)
    names = GENRE_STICKERS.get(genre) or ["sparkles", "star", "thumbs"]
    out = []
    spots = [(0.78, 0.26), (0.22, 0.30), (0.80, 0.62), (0.20, 0.64), (0.50, 0.20)]
    t = rng.uniform(1.6, 3.2)
    for i in range(max(1, min(count, int(seconds // 7)))):
        if t + 2.2 > seconds - 1.2:
            break
        pos = spots[i % len(spots)]
        out.append({"code": rng.choice(names), "at": round(t, 2), "dur": round(rng.uniform(2.0, 3.0), 2),
                    "x": pos[0], "y": pos[1], "size": rng.uniform(0.11, 0.16)})
        t += rng.uniform(4.5, 7.5)
    return out
