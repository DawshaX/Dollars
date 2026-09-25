"""
🏷️ مكتبة الملصقات والميمز — Dollars Studio (ملكية كاملة 100%)
==============================================================
كل ملصق هنا **مرسوم بالكود** (PIL) — مش صورة من النت، مش إيموجي محمي، مش أي
حاجة ليها حقوق. دي «لغة بصرية» خاصة بالقناة: شخصياتنا + رموزنا + ميمز بتاعتنا.

الواجهة:
    python tools/make_stickers.py            # يبني assets/stickers + assets/memes
    python tools/build_library.py            # يحدّث content/library.json
"""
from __future__ import annotations

import json
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
SS = 4                      # تكبير للرسم ثم تصغير ⇒ حواف ناعمة
SIZE = 512

INK = (27, 27, 31, 255)
CLAY = (201, 139, 90, 255)
CLAY_D = (156, 100, 60, 255)
CLOUD = (238, 240, 255, 255)
CLOUD_D = (198, 204, 238, 255)
PAPER = (242, 227, 198, 255)
PAPER_D = (205, 187, 154, 255)
YEL = (255, 209, 102, 255)
CORAL = (255, 107, 107, 255)
MINT = (78, 205, 196, 255)
VIOLET = (155, 93, 229, 255)
WHITE = (255, 255, 255, 255)
RED = (239, 71, 111, 255)
BLUE = (120, 190, 255, 255)
GREEN = (110, 220, 150, 255)


def canvas(bg=None):
    img = Image.new("RGBA", (SIZE * SS, SIZE * SS), bg or (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def done(img, name, out: pathlib.Path):
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{name}.png"
    img.save(p)
    return p


def eye(d, cx, cy, r, pupil=INK, shine=True, closed=False, wide=False):
    if closed:
        d.arc([cx - r, cy - r * 0.7, cx + r, cy + r * 0.7], 200, 340, fill=INK, width=max(2, int(r * 0.35)))
        return
    rr = r * (1.25 if wide else 1.0)
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=WHITE, outline=INK, width=max(2, int(r * 0.18)))
    pr = rr * (0.55 if not wide else 0.4)
    d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=pupil)
    if shine:
        d.ellipse([cx - pr * 1.15, cy - pr * 1.2, cx - pr * 0.15, cy - pr * 0.25], fill=WHITE)


def smile(d, cx, cy, w, h, happy=True, width=6):
    if happy:
        d.arc([cx - w, cy - h, cx + w, cy + h], 20, 160, fill=INK, width=width)
    else:
        d.arc([cx - w, cy - h, cx + w, cy + h], 200, 340, fill=INK, width=width)


def heart_path(d, cx, cy, s, fill):
    d.ellipse([cx - s, cy - s * 0.95, cx, cy + s * 0.05], fill=fill)
    d.ellipse([cx, cy - s * 0.95, cx + s, cy + s * 0.05], fill=fill)
    d.polygon([(cx - s * 1.0, cy - s * 0.15), (cx + s * 1.0, cy - s * 0.15), (cx, cy + s * 1.05)], fill=fill)


def star_path(pts=5, r1=1.0, r2=0.42):
    import math
    out = []
    for i in range(pts * 2):
        ang = math.pi / 2 + i * math.pi / pts
        r = r1 if i % 2 == 0 else r2
        out.append((math.cos(ang) * r, -math.sin(ang) * r))
    return out


def star(d, cx, cy, s, fill=YEL, outline=INK):
    poly = [(cx + x * s, cy + y * s) for x, y in star_path()]
    d.polygon(poly, fill=fill, outline=outline, width=max(2, int(s * 0.06)))


def burst(d, cx, cy, s, fill=YEL):
    import math
    poly = []
    for i in range(24):
        ang = i * math.pi / 12
        r = s if i % 2 == 0 else s * 0.62
        poly.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    d.polygon(poly, fill=fill, outline=INK, width=max(2, int(s * 0.045)))


def cloud_shape(d, cx, cy, s, fill=CLOUD, outline=INK, w=None):
    w = w or max(3, int(s * 0.06))
    d.ellipse([cx - s, cy - s * 0.55, cx - s * 0.25, cy + s * 0.5], fill=fill, outline=outline, width=w)
    d.ellipse([cx - s * 0.55, cy - s * 0.95, cx + s * 0.35, cy + s * 0.35], fill=fill, outline=outline, width=w)
    d.ellipse([cx + s * 0.05, cy - s * 0.6, cx + s, cy + s * 0.5], fill=fill, outline=outline, width=w)
    d.rectangle([cx - s * 0.85, cy - s * 0.05, cx + s * 0.85, cy + s * 0.5], fill=fill)
    d.line([cx - s * 0.92, cy + s * 0.5, cx + s * 0.92, cy + s * 0.5], fill=outline, width=w)


# ───────────────────────────── ملصقات الشخصيات ─────────────────────────────

def st_nono(mood="happy"):
    img, d = canvas()
    cx, cy, r = SIZE * SS / 2, SIZE * SS / 2 + 12 * SS, SIZE * SS * 0.34
    d.ellipse([cx - r, cy - r * 0.95, cx + r, cy + r], fill=CLAY, outline=INK, width=5 * SS)
    d.ellipse([cx - r * 0.75, cy - r * 0.6, cx - r * 0.05, cy + r * 0.1], fill=(232, 179, 133, 255))
    ex, ey, er = r * 0.34, cy - r * 0.18, r * 0.20
    if mood == "love":
        d.ellipse([cx - r, cy - r * 1.5, cx + r, cy + r * 0.6], fill=(0, 0, 0, 0))
        d.ellipse([cx - r, cy - r * 0.95, cx + r, cy + r], fill=CLAY, outline=INK, width=5 * SS)
        heart_path(d, cx - ex, ey, er * 1.1, RED); heart_path(d, cx + ex, ey, er * 1.1, RED)
    elif mood == "sleepy":
        eye(d, cx - ex, ey, er, closed=True); eye(d, cx + ex, ey, er, closed=True)
        smile(d, cx, cy + r * 0.25, r * 0.2, r * 0.12, width=4 * SS)
    else:
        wide = mood == "shock"
        eye(d, cx - ex, ey, er, wide=wide); eye(d, cx + ex, ey, er, wide=wide)
        if mood == "happy":
            smile(d, cx, cy + r * 0.16, r * 0.3, r * 0.22, width=5 * SS)
        elif mood == "shock":
            d.ellipse([cx - r * 0.16, cy + r * 0.22, cx + r * 0.16, cy + r * 0.56], fill=INK)
        elif mood == "sad":
            smile(d, cx, cy + r * 0.5, r * 0.3, r * 0.2, happy=False, width=5 * SS)
            d.ellipse([cx + ex * 1.5, cy + r * 0.05, cx + ex * 1.5 + r * 0.14, cy + r * 0.35], fill=BLUE)
    for sx, sy in ((-r * 0.62, r * 0.72), (r * 0.62, r * 0.72)):
        d.ellipse([cx + sx - r * 0.18, cy + sy - r * 0.1, cx + sx + r * 0.18, cy + sy + r * 0.2],
                  fill=CLAY_D, outline=INK, width=4 * SS)
    return img


def st_koko(mood="happy"):
    img, d = canvas()
    cx, cy, s = SIZE * SS / 2, SIZE * SS / 2 + 8 * SS, SIZE * SS * 0.34
    cloud_shape(d, cx, cy, s, fill=CLOUD, outline=CLOUD_D)
    d.ellipse([cx - s * 0.66, cy - s * 0.62, cx + s * 0.66, cy + s * 0.52],
              fill=(0, 0, 0, 0))                                    # الوجه جوّه السحابة
    d.ellipse([cx - s * 0.66, cy - s * 0.62, cx + s * 0.66, cy + s * 0.52], fill=CLOUD)
    ex, ey, er = s * 0.3, cy - s * 0.12, s * 0.17
    if mood == "sleep":
        eye(d, cx - ex, ey, er, closed=True); eye(d, cx + ex, ey, er, closed=True)
        smile(d, cx, cy + s * 0.2, s * 0.14, s * 0.08, width=4 * SS)
    else:
        eye(d, cx - ex, ey, er); eye(d, cx + ex, ey, er)
        smile(d, cx, cy + s * 0.12, s * 0.2, s * 0.14, width=5 * SS)
    d.polygon([(cx - s * 0.62, cy - s * 0.5), (cx - s * 0.3, cy - s * 0.95),
               (cx - s * 0.12, cy - s * 0.45)], fill=CLOUD, outline=CLOUD_D, width=4 * SS)
    d.polygon([(cx + s * 0.62, cy - s * 0.5), (cx + s * 0.3, cy - s * 0.95),
               (cx + s * 0.12, cy - s * 0.45)], fill=CLOUD, outline=CLOUD_D, width=4 * SS)
    for i in range(3):
        star(d, cx + s * (0.9 + 0.16 * i), cy - s * (0.15 + 0.3 * i), s * 0.1 * (1 - i * 0.18), YEL, INK)
    return img


def st_paper_man(mood="wave"):
    img, d = canvas()
    cx, cy = SIZE * SS / 2, SIZE * SS / 2
    w, h = SIZE * SS * 0.30, SIZE * SS * 0.42
    d.rounded_rectangle([cx - w, cy - h, cx + w, cy + h], radius=14 * SS, fill=PAPER,
                        outline=PAPER_D, width=5 * SS)
    d.line([cx - w, cy - h * 0.35, cx + w, cy - h * 0.35], fill=PAPER_D, width=4 * SS)
    ex, ey, er = w * 0.42, cy - h * 0.05, w * 0.2
    eye(d, cx - ex, ey, er); eye(d, cx + ex, ey, er)
    if mood == "wave":
        smile(d, cx, cy + h * 0.22, w * 0.4, h * 0.16, width=5 * SS)
        d.line([cx + w, cy - h * 0.1, cx + w * 1.7, cy - h * 0.6], fill=PAPER_D, width=10 * SS)
        d.ellipse([cx + w * 1.6, cy - h * 0.78, cx + w * 2.1, cy - h * 0.42], fill=PAPER, outline=PAPER_D, width=5 * SS)
    else:  # facepalm
        smile(d, cx, cy + h * 0.4, w * 0.35, h * 0.15, happy=False, width=5 * SS)
        d.ellipse([cx + w * 0.1, cy - h * 0.55, cx + w * 1.5, cy + h * 0.35], fill=PAPER, outline=PAPER_D, width=6 * SS)
    return img


# ───────────────────────────── ملصقات رمزية ─────────────────────────────

def st_heart(): 
    img, d = canvas(); heart_path(d, SIZE * SS / 2, SIZE * SS / 2 + 10 * SS, SIZE * SS * 0.33, RED); return img


def st_heart_broken():
    img, d = canvas(); s = SIZE * SS * 0.33
    heart_path(d, SIZE * SS / 2, SIZE * SS / 2 + 10 * SS, s, RED)
    cx, cy = SIZE * SS / 2, SIZE * SS / 2 + 10 * SS
    d.polygon([(cx, cy - s * 0.95), (cx - s * 0.3, cy - s * 0.1), (cx + s * 0.22, cy + s * 0.12),
               (cx - s * 0.12, cy + s * 1.05)], fill=(0, 0, 0, 0))
    return img


def st_star():
    img, d = canvas(); star(d, SIZE * SS / 2, SIZE * SS / 2, SIZE * SS * 0.36); return img


def st_sparkle():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.30
    for i, rot in ((0, 0), (1, 0.5), (2, 1.1)):
        r = s * (1 - i * 0.28)
        import math
        pts = []
        for j in range(8):
            ang = rot + j * math.pi / 4
            rr = r if j % 2 == 0 else r * 0.25
            pts.append((c + math.cos(ang) * rr, c + math.sin(ang) * rr))
        d.polygon(pts, fill=WHITE if i == 0 else YEL)
    return img


def st_question():
    img, d = canvas()
    d.rounded_rectangle([SIZE * SS * 0.1, SIZE * SS * 0.1, SIZE * SS * 0.9, SIZE * SS * 0.9],
                        radius=60 * SS, fill=YEL, outline=INK, width=8 * SS)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(SIZE * SS * 0.62))
    except Exception:
        f = ImageFont.load_default()
    d.text((SIZE * SS / 2, SIZE * SS * 0.46), "?", font=f, fill=INK, anchor="mm")
    return img


def st_exclaim():
    img, d = canvas()
    d.rounded_rectangle([SIZE * SS * 0.16, SIZE * SS * 0.08, SIZE * SS * 0.84, SIZE * SS * 0.92],
                        radius=70 * SS, fill=CORAL, outline=INK, width=8 * SS)
    d.rounded_rectangle([SIZE * SS * 0.42, SIZE * SS * 0.2, SIZE * SS * 0.58, SIZE * SS * 0.62],
                        radius=20 * SS, fill=WHITE)
    d.ellipse([SIZE * SS * 0.41, SIZE * SS * 0.68, SIZE * SS * 0.59, SIZE * SS * 0.84], fill=WHITE)
    return img


def st_arrow_right():
    img, d = canvas(); c = SIZE * SS / 2
    d.polygon([(c - 0.4 * SIZE * SS, c - 0.10 * SIZE * SS), (c + 0.05 * SIZE * SS, c - 0.10 * SIZE * SS),
               (c + 0.05 * SIZE * SS, c - 0.26 * SIZE * SS), (c + 0.42 * SIZE * SS, c),
               (c + 0.05 * SIZE * SS, c + 0.26 * SIZE * SS), (c + 0.05 * SIZE * SS, c + 0.10 * SIZE * SS),
               (c - 0.4 * SIZE * SS, c + 0.10 * SIZE * SS)], fill=MINT, outline=INK, width=6 * SS)
    return img


def st_arrow_curve():
    img, d = canvas(); c = SIZE * SS / 2
    d.arc([c - 0.35 * SIZE * SS, c - 0.45 * SIZE * SS, c + 0.35 * SIZE * SS, c + 0.25 * SIZE * SS],
          180, 20, fill=VIOLET, width=26 * SS)
    d.polygon([(c + 0.30 * SIZE * SS, c - 0.10 * SIZE * SS), (c + 0.46 * SIZE * SS, c + 0.06 * SIZE * SS),
               (c + 0.16 * SIZE * SS, c + 0.12 * SIZE * SS)], fill=VIOLET)
    return img


def st_crown():
    img, d = canvas(); c = SIZE * SS / 2
    d.polygon([(c - 0.36 * SIZE * SS, c + 0.22 * SIZE * SS), (c - 0.30 * SIZE * SS, c - 0.26 * SIZE * SS),
               (c - 0.10 * SIZE * SS, c + 0.02 * SIZE * SS), (c, c - 0.34 * SIZE * SS),
               (c + 0.10 * SIZE * SS, c + 0.02 * SIZE * SS), (c + 0.30 * SIZE * SS, c - 0.26 * SIZE * SS),
               (c + 0.36 * SIZE * SS, c + 0.22 * SIZE * SS)], fill=YEL, outline=INK, width=7 * SS)
    return img


def st_cloud():
    img, d = canvas(); cloud_shape(d, SIZE * SS / 2, SIZE * SS / 2 + 20 * SS, SIZE * SS * 0.33); return img


def st_rain_cloud():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.30
    cloud_shape(d, c, c - s * 0.25, s)
    for i in range(3):
        x = c - s * 0.5 + i * s * 0.5
        d.line([x, c + s * 0.6, x - s * 0.12, c + s * 1.05], fill=BLUE, width=10 * SS)
    return img


def st_moon():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.34
    d.ellipse([c - s, c - s, c + s, c + s], fill=(255, 244, 214, 255))
    d.ellipse([c - s * 1.25, c - s * 1.2, c + s * 0.35, c + s * 0.75], fill=(0, 0, 0, 0))
    d.ellipse([c - s * 0.6, c - s * 0.35, c - s * 0.3, c - s * 0.05], fill=(224, 208, 170, 255))
    return img


def st_sun():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.20
    for i in range(12):
        import math
        a = i * math.pi / 6
        d.line([c + math.cos(a) * s * 1.35, c + math.sin(a) * s * 1.35,
                c + math.cos(a) * s * 1.9, c + math.sin(a) * s * 1.9], fill=YEL, width=14 * SS)
    d.ellipse([c - s, c - s, c + s, c + s], fill=(255, 196, 61, 255), outline=(255, 160, 40, 255), width=6 * SS)
    return img


def st_flame():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.34
    d.polygon([(c, c - s * 1.05), (c + s * 0.75, c + s * 0.3), (c + s * 0.35, c + s * 0.9),
               (c - s * 0.35, c + s * 0.9), (c - s * 0.75, c + s * 0.3)], fill=(255, 140, 40, 255),
              outline=(224, 90, 20, 255), width=6 * SS)
    d.polygon([(c, c - s * 0.2), (c + s * 0.38, c + s * 0.35), (c, c + s * 0.72),
               (c - s * 0.38, c + s * 0.35)], fill=YEL)
    return img


def st_droplet():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.34
    d.polygon([(c, c - s * 1.05), (c + s * 0.8, c + s * 0.4), (c - s * 0.8, c + s * 0.4)], fill=BLUE)
    d.ellipse([c - s * 0.8, c - s * 0.35, c + s * 0.8, c + s * 1.0], fill=BLUE)
    return img


def st_note():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.3
    d.ellipse([c - s * 0.9, c + s * 0.45, c - s * 0.2, c + s * 1.0], fill=VIOLET)
    d.ellipse([c + s * 0.1, c + s * 0.2, c + s * 0.8, c + s * 0.75], fill=VIOLET)
    d.rectangle([c - s * 0.35, c - s * 0.85, c - s * 0.2, c + s * 0.85], fill=VIOLET)
    d.rectangle([c + s * 0.65, c - s * 1.1, c + s * 0.8, c + s * 0.6], fill=VIOLET)
    d.rectangle([c - s * 0.35, c - s * 1.1, c + s * 0.8, c - s * 0.9], fill=VIOLET)
    return img


def st_burst():
    img, d = canvas(); burst(d, SIZE * SS / 2, SIZE * SS / 2, SIZE * SS * 0.42); return img


def st_speed_lines():
    img, d = canvas(); c = SIZE * SS / 2
    for i in range(6):
        y = c - 0.3 * SIZE * SS + i * 0.12 * SIZE * SS
        d.line([0, y, SIZE * SS * (0.45 + 0.08 * (i % 3)), y], fill=WHITE, width=16 * SS)
    return img


def st_ring():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.32
    d.ellipse([c - s, c - s, c + s, c + s], outline=YEL, width=26 * SS)
    return img


def st_check():
    img, d = canvas(); c = SIZE * SS / 2
    d.line([c - 0.3 * SIZE * SS, c + 0.02 * SIZE * SS, c - 0.08 * SIZE * SS, c + 0.26 * SIZE * SS,
            c + 0.32 * SIZE * SS, c - 0.26 * SIZE * SS], fill=GREEN, width=34 * SS, joint="curve")
    return img


def st_cross():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.28
    d.line([c - s, c - s, c + s, c + s], fill=CORAL, width=32 * SS)
    d.line([c + s, c - s, c - s, c + s], fill=CORAL, width=32 * SS)
    return img


def st_badge_new():
    img, d = canvas(); burst(d, SIZE * SS / 2, SIZE * SS / 2, SIZE * SS * 0.44, CORAL)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(SIZE * SS * 0.22))
    except Exception:
        f = ImageFont.load_default()
    d.text((SIZE * SS / 2, SIZE * SS / 2), "NEW", font=f, fill=WHITE, anchor="mm")
    return img


def st_zzz():
    img, d = canvas()
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(SIZE * SS * 0.4))
    except Exception:
        f = ImageFont.load_default()
    for i, (x, y, k) in enumerate([(0.28, 0.62, 1.0), (0.5, 0.42, 0.75), (0.68, 0.26, 0.55)]):
        d.text((x * SIZE * SS, y * SIZE * SS), "z", font=f, fill=VIOLET if i == 0 else CLOUD_D, anchor="mm")
    return img


def st_anger():
    img, d = canvas(); c = SIZE * SS / 2
    for i in range(3):
        d.line([c - 0.3 * SIZE * SS, c - 0.12 * SIZE * SS + i * 0.2 * SIZE * SS,
                c, c - 0.02 * SIZE * SS + i * 0.2 * SIZE * SS,
                c - 0.3 * SIZE * SS, c + 0.08 * SIZE * SS + i * 0.2 * SIZE * SS], fill=RED, width=22 * SS)
    return img


def st_laugh():
    img, d = canvas(); c, s = SIZE * SS / 2, SIZE * SS * 0.33
    d.ellipse([c - s, c - s, c + s, c + s], fill=YEL, outline=INK, width=8 * SS)
    d.arc([c - s * 0.55, c - s * 0.45, c + s * 0.55, c + s * 0.4], 20, 160, fill=INK, width=16 * SS)
    for sx in (-1, 1):
        d.ellipse([c + sx * s * 0.75 - s * 0.12, c + s * 0.25, c + sx * s * 0.75 + s * 0.12, c + s * 0.75], fill=BLUE)
    eye(d, c - s * 0.35, c - s * 0.35, s * 0.14); eye(d, c + s * 0.35, c - s * 0.35, s * 0.14)
    return img


def st_speech():
    img, d = canvas(); c = SIZE * SS / 2
    d.rounded_rectangle([c - 0.42 * SIZE * SS, c - 0.34 * SIZE * SS, c + 0.42 * SIZE * SS, c + 0.16 * SIZE * SS],
                        radius=40 * SS, fill=WHITE, outline=INK, width=8 * SS)
    d.polygon([(c - 0.12 * SIZE * SS, c + 0.16 * SIZE * SS), (c + 0.06 * SIZE * SS, c + 0.42 * SIZE * SS),
               (c + 0.14 * SIZE * SS, c + 0.14 * SIZE * SS)], fill=WHITE, outline=INK, width=8 * SS)
    return img


def st_thought():
    img, d = canvas(); c = SIZE * SS / 2
    cloud_shape(d, c, c - 0.06 * SIZE * SS, SIZE * SS * 0.34, WHITE, INK)
    for i, (dx, dy, r) in enumerate([(-0.22, 0.28, 0.05), (-0.3, 0.38, 0.032)]):
        d.ellipse([c + dx * SIZE * SS - r * SIZE * SS, c + dy * SIZE * SS - r * SIZE * SS,
                   c + dx * SIZE * SS + r * SIZE * SS, c + dy * SIZE * SS + r * SIZE * SS],
                  fill=WHITE, outline=INK, width=6 * SS)
    return img


STICKERS = {
    "nono_happy": lambda: st_nono("happy"), "nono_shock": lambda: st_nono("shock"),
    "nono_love": lambda: st_nono("love"), "nono_sad": lambda: st_nono("sad"),
    "nono_sleepy": lambda: st_nono("sleepy"),
    "koko_happy": lambda: st_koko("happy"), "koko_sleep": lambda: st_koko("sleep"),
    "paper_man": lambda: st_paper_man("wave"), "paper_man_facepalm": lambda: st_paper_man("facepalm"),
    "heart": st_heart, "heart_broken": st_heart_broken, "star": st_star, "sparkle": st_sparkle,
    "question": st_question, "exclaim": st_exclaim, "arrow_right": st_arrow_right,
    "arrow_curve": st_arrow_curve, "crown": st_crown, "cloud": st_cloud, "rain_cloud": st_rain_cloud,
    "moon": st_moon, "sun": st_sun, "flame": st_flame, "droplet": st_droplet, "note": st_note,
    "burst": st_burst, "speed_lines": st_speed_lines, "ring": st_ring, "check": st_check,
    "cross": st_cross, "badge_new": st_badge_new, "zzz": st_zzz, "anger": st_anger,
    "laugh": st_laugh, "speech": st_speech, "thought": st_thought,
}

# مواضع الاستخدام المقترحة (يستخدمها المجمّع)
STICKER_USES = {
    "reaction": ["nono_happy", "nono_shock", "nono_love", "nono_sad", "nono_sleepy",
                 "koko_happy", "koko_sleep", "paper_man", "paper_man_facepalm",
                 "laugh", "anger", "zzz"],
    "emotion": ["heart", "heart_broken", "star", "sparkle", "flame", "droplet", "moon", "sun", "cloud"],
    "ui": ["question", "exclaim", "arrow_right", "arrow_curve", "crown", "check", "cross",
           "badge_new", "ring", "burst", "speed_lines", "speech", "thought", "note", "rain_cloud"],
}


# ───────────────────────────── قوالب الميمز ─────────────────────────────

MEME_TEMPLATES = {
    # اسم القالب: (الرسمة، وصف الاستخدام، أماكن الكتابة)
    "reaction_face_big": ("nono_shock", "وش كبير + جملة تحت — لأي صدمة أو مفاجأة",
                          {"top": (0.06, 0.10), "bottom": (0.78, 0.96)}),
    "character_center": ("nono_happy", "الشخصية في النص + عنوان فوق وتحت",
                         {"top": (0.05, 0.18), "bottom": (0.80, 0.95)}),
    "side_by_side": ("paper_man", "قبل/بعد: صورتين جنب بعض + سطر تحت",
                     {"left": (0.04, 0.46), "right": (0.54, 0.96), "bottom": (0.82, 0.96)}),
    "calm_koko": ("koko_sleep", "هادئ للنوم: قطة السحاب + سطر ناعم",
                  {"top": (0.08, 0.22), "bottom": (0.80, 0.94)}),
    "zoom_question": ("question", "سؤال يشدّ المشاهد في أول ثانية",
                      {"center": (0.25, 0.75)}),
    "celebration_burst": ("badge_new", "احتفال/إعلان — شرايط ولون قوي",
                          {"top": (0.05, 0.2), "bottom": (0.8, 0.95)}),
}


def build_memes(out: pathlib.Path, size: int = 1080):
    """قوالب ميمز فاضية (خلفية + شخصية + شرايط كتابة) — النص يُكتب وقت المونتاج."""
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for name, (sticker, use, areas) in MEME_TEMPLATES.items():
        img = Image.new("RGBA", (size, size), (18, 16, 28, 255))
        st = Image.open(ROOT / "assets" / "stickers" / f"{sticker}.png").convert("RGBA")
        st = st.resize((int(size * 0.42), int(size * 0.42)), Image.LANCZOS)
        img.alpha_composite(st, (int(size * 0.5 - size * 0.21), int(size * 0.28)))
        d = ImageDraw.Draw(img)
        for key, (y0, y1) in areas.items():
            d.rounded_rectangle([size * 0.06, size * y0, size * 0.94, size * y1],
                                radius=22, fill=(0, 0, 0, 140))
        p = out / f"{name}.png"
        img.convert("RGB").save(p)
        made.append(p)
    meta = {name: {"sticker": s, "use": u, "text_areas": a}
            for name, (s, u, a) in MEME_TEMPLATES.items()}
    (out / "index.json").write_text(json.dumps(
        {"note": "قوالب ميمز Dollars — تركيبات أصلية بلا أي حقوق.",
         "base_size": size, "templates": meta}, ensure_ascii=False, indent=2), encoding="utf-8")
    return made


def main():
    stick = ROOT / "assets" / "stickers"
    paths = []
    for name, fn in STICKERS.items():
        paths.append(done(fn(), name, stick))
    (stick / "index.json").write_text(json.dumps(
        {"note": "ملصقات Dollars — مرسومة بالكود 100%، ملكية كاملة، بلا حقوق.",
         "license": "owned-generated", "size": SIZE, "count": len(paths),
         "uses": STICKER_USES, "files": sorted(p.name for p in paths)},
        ensure_ascii=False, indent=2), encoding="utf-8")
    memes = build_memes(ROOT / "assets" / "memes")
    print(f"✅ {len(paths)} ملصق + {len(memes)} قالب ميمز")


if __name__ == "__main__":
    main()
