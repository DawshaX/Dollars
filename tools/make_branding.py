"""
🎨 هوية القناة — Dollars Studio (مرسومة بالكود 100%)
====================================================
بيطلّع كل صور القناة بمقاسات يوتيوب الرسمية:
    أفاتار 800×800 · بانر 2560×1440 · علامة مائية 150×150 · شاشة نهاية 1280×720
    + أيقونة الشورتس + قالب الغلاف الافتراضي

كل حاجة مرسومة بالكود ⇒ ملكنا، ومفيش أي حقوق على أي حد.
    python tools/make_branding.py            # يبني assets/brand/
"""
from __future__ import annotations

import json
import math
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "brand"

# 🎨 الألوان الرسمية للقناة (هوية موحّدة)
C = {
    "night": (10, 14, 30),
    "deep": (16, 22, 48),
    "teal": (78, 205, 196),
    "violet": (155, 93, 229),
    "gold": (255, 196, 61),
    "moon": (238, 240, 255),
    "white": (255, 255, 255),
    "ink": (18, 20, 34),
}

NAME = "DOLLARS"
TAGLINE = "SLEEP • STORIES • SATISFYING"


def _font(size: int, bold: bool = True):
    names = ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf") if bold else ("DejaVuSans.ttf",)
    for n in names:
        for base in ("/usr/share/fonts/truetype/dejavu/", "/usr/share/fonts/truetype/liberation/",
                     "/System/Library/Fonts/Supplemental/"):
            p = pathlib.Path(base + n)
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except Exception:
                    pass
    return ImageFont.load_default()


def _disc(d: ImageDraw.ImageDraw, cx, cy, r, fill, outline=None, w=0):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=w)


def _star(d, cx, cy, r, fill, points=4):
    poly = []
    for i in range(points * 2):
        a = -math.pi / 2 + i * math.pi / points
        rr = r if i % 2 == 0 else r * 0.34
        poly.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    d.polygon(poly, fill=fill)


def _moon_symbol(img: Image.Image, cx, cy, r):
    """شعارنا: هلال بيحضن بحيرة + نجمة — يرمز للنوم والحِكايات."""
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    _disc(d, cx, cy, r, C["moon"] + (255,))
    _disc(d, cx - r * 0.42, cy - r * 0.22, r * 0.92, (0, 0, 0, 0))
    # بحيرة/خط موج تحته
    d.rounded_rectangle([cx - r * 1.25, cy + r * 0.72, cx + r * 1.25, cy + r * 0.95],
                        radius=r * 0.12, fill=C["teal"] + (230,))
    # نجوم صغيرة
    _star(d, cx + r * 0.85, cy - r * 0.55, r * 0.20, C["gold"] + (255,))
    _star(d, cx + r * 1.15, cy - r * 0.05, r * 0.12, C["moon"] + (220,))
    img.alpha_composite(lay)


def _gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size, top)
    d = ImageDraw.Draw(img)
    for y in range(h):
        k = y / max(1, h - 1)
        col = tuple(int(top[i] * (1 - k) + bottom[i] * k) for i in range(3))
        d.line([(0, y), (w, y)], fill=col)
    return img


def avatar(size=800) -> pathlib.Path:
    img = _gradient((size, size), C["night"], C["deep"]).convert("RGBA")
    d = ImageDraw.Draw(img)
    for i, r in enumerate((0.46, 0.36, 0.27)):
        d.ellipse([size / 2 - size * r, size / 2 - size * r, size / 2 + size * r, size / 2 + size * r],
                  outline=(*(C["teal"] if i == 0 else C["violet"]), 70), width=int(size * 0.006))
    _moon_symbol(img, size * 0.5, size * 0.44, size * 0.19)
    f = _font(int(size * 0.11))
    t = NAME
    box = d.textbbox((0, 0), t, font=f)
    d.text(((size - (box[2] - box[0])) / 2, size * 0.76), t, font=f, fill=C["white"] + (255,))
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "avatar_800.png"
    img.convert("RGB").save(p)
    return p


def banner(size=(2560, 1440)) -> pathlib.Path:
    w, h = size
    img = _gradient(size, (6, 9, 22), C["deep"]).convert("RGBA")
    d = ImageDraw.Draw(img)
    # نجوم + هالة قمر
    for i in range(260):
        x = (i * 977) % w
        y = (i * 613) % int(h * 0.7)
        r = 1.2 + (i % 3) * 0.9
        a = 90 + (i % 5) * 30
        d.ellipse([x, y, x + r, y + r], fill=(255, 255, 255, a))
    _disc(d, w * 0.80, h * 0.30, h * 0.16, (255, 246, 214, 28))
    _moon_symbol(img, w * 0.80, h * 0.30, h * 0.085)
    # موجة أفقية (خط الرحلة)
    for k, col in ((0, C["teal"]), (1, C["violet"])):
        pts = [(x, h * 0.66 + math.sin(x / 220 + k) * 26 + k * 26) for x in range(0, w, 12)]
        d.line(pts, fill=col + (170,), width=6 - k * 2, joint="curve")
    f1 = _font(200)
    box = d.textbbox((0, 0), NAME, font=f1)
    d.text((w * 0.10, h * 0.40), NAME, font=f1, fill=C["white"] + (255,))
    f2 = _font(74)
    d.text((w * 0.105, h * 0.40 + (box[3] - box[1]) + 36), TAGLINE, font=f2, fill=C["teal"] + (235,))
    f3 = _font(46)
    d.text((w * 0.105, h * 0.40 + (box[3] - box[1]) + 150),
           "New ambience every day  ·  a story every week  ·  shorts every hour",
           font=f3, fill=(210, 216, 240, 210))
    p = OUT / "banner_2560x1440.png"
    img.convert("RGB").save(p)
    return p


def watermark(size=150) -> pathlib.Path:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _moon_symbol(img, size * 0.5, size * 0.46, size * 0.28)
    p = OUT / "watermark_150.png"
    img.save(p)
    return p


def endcard(size=(1280, 720)) -> pathlib.Path:
    w, h = size
    img = _gradient(size, (8, 11, 26), (18, 24, 52)).convert("RGBA")
    d = ImageDraw.Draw(img)
    _moon_symbol(img, w * 0.5, h * 0.34, h * 0.13)
    f1 = _font(96)
    t = "THANKS FOR WATCHING"
    box = d.textbbox((0, 0), t, font=f1)
    d.text(((w - (box[2] - box[0])) / 2, h * 0.52), t, font=f1, fill=C["white"] + (255,))
    f2 = _font(52)
    t2 = "Subscribe for a calm night, every night"
    box2 = d.textbbox((0, 0), t2, font=f2)
    d.text(((w - (box2[2] - box2[0])) / 2, h * 0.52 + (box[3] - box[1]) + 30), t2, font=f2,
           fill=C["teal"] + (235,))
    # مكان عنصرَي يوتيوب (فيديو/بلايليست) — نسيبهم فاضيين عشان الاستوديو يحطّهم
    for i, x in enumerate((w * 0.18, w * 0.60)):
        d.rounded_rectangle([x, h * 0.76, x + w * 0.24, h * 0.90], radius=14,
                            outline=(255, 255, 255, 90), width=4)
        lab = "LATEST VIDEO" if i == 0 else "BEST PLAYLIST"
        d.text((x + 18, h * 0.76 + 12), lab, font=_font(30), fill=(220, 226, 245, 200))
    p = OUT / "endcard_1280x720.png"
    img.convert("RGB").save(p)
    return p


def short_icon(size=800) -> pathlib.Path:
    img = _gradient((size, size), C["night"], (32, 22, 60)).convert("RGBA")
    d = ImageDraw.Draw(img)
    _moon_symbol(img, size * 0.5, size * 0.42, size * 0.2)
    f = _font(int(size * 0.13))
    t = "SHORTS"
    box = d.textbbox((0, 0), t, font=f)
    d.text(((size - (box[2] - box[0])) / 2, size * 0.70), t, font=f, fill=C["gold"] + (255,))
    p = OUT / "shorts_icon_800.png"
    img.convert("RGB").save(p)
    return p


def thumb_template(size=(1280, 720)) -> pathlib.Path:
    w, h = size
    img = _gradient(size, (10, 13, 28), (20, 26, 54)).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([w * 0.05, h * 0.66, w * 0.95, h * 0.94], radius=18,
                        fill=(0, 0, 0, 140), outline=(255, 255, 255, 60), width=3)
    d.text((w * 0.07, h * 0.70), "ضع هنا سطر الغلاف (3-5 كلمات كبيرة)", font=_font(54),
           fill=(235, 238, 250, 230))
    d.rounded_rectangle([w * 0.05, h * 0.06, w * 0.34, h * 0.22], radius=14,
                        fill=C["gold"] + (220,))
    d.text((w * 0.075, h * 0.09), "10 HOURS", font=_font(56), fill=C["ink"] + (255,))
    p = OUT / "thumb_template_1280x720.png"
    img.convert("RGB").save(p)
    return p


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "avatar": avatar(), "banner": banner(), "watermark": watermark(),
        "endcard": endcard(), "shorts_icon": short_icon(), "thumb_template": thumb_template(),
    }
    index = {
        "note": "هوية Dollars — مرسومة بالكود 100% (ملكنا · بلا أي حقوق).",
        "name": NAME, "tagline": TAGLINE, "colors": {k: list(v) for k, v in C.items()},
        "files": {k: str(v.relative_to(ROOT)) for k, v in files.items()},
        "youtube_sizes": {"avatar": "800×800 (يُعرض دائري)", "banner": "2560×1440 (المنطقة الآمنة 1546×423)",
                          "watermark": "150×150", "endcard": "1280×720", "thumbnail": "1280×720"},
    }
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


if __name__ == "__main__":
    i = build()
    print("✅ الهوية اتبنت:")
    for k, v in i["files"].items():
        print(f"   • {k}: {v}")
