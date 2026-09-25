"""
🎭 محرّك تحريك الشخصيات (2.5D Cutout) — Dollars Studio
=======================================================
بيحوّل ملصقاتنا الثابتة (نونو · كوكو · الرجل الورقي) لشخصيات **بتعيش وبتتحرك**:
تنفّس · نطّ · انضغاط وتمدّد (squash & stretch) · ميل · دوران · قلب الاتجاه ·
**رمشة** · دخول/خروج · ظل تلامس · ودمج مع المشهد بإضاءة تخصه.

كل حاجة من أصولنا المرسومة بالكود ⇒ صفر حقوق. والحركة كلها دوال دورية أو خطط
مُعطاة ⇒ الحلقة تفضل مثالية.

الواجهة:
    from engine import cutout
    actor = cutout.Actor("nono_happy", x=0.3, y=0.72, scale=0.34, move="hop", phase=0.2)
    layer = cutout.Layer(w=960, h=540)          # طبقة شفافة فوق المشهد
    layer.add(actor)
    layer.compose(bg_float, t)                  # يرسم الظلال والحركة فوق المشهد
"""
from __future__ import annotations

import functools
import math
import pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
STICKERS = ROOT / "assets" / "stickers"
TAU = 2.0 * math.pi

# أزواج الرمشة: الاسم الأساسي → نسخة العين المقفولة
BLINK_PAIRS = {
    "nono_happy": "nono_sleepy", "nono_shock": "nono_sleepy", "nono_love": "nono_sleepy",
    "nono_sad": "nono_sleepy", "koko_happy": "koko_sleep", "paper_man": "paper_man",
    "paper_man_facepalm": "paper_man_facepalm",
}


@functools.lru_cache(maxsize=64)
def load_sprite(name: str) -> Image.Image:
    p = STICKERS / f"{name}.png"
    if not p.exists():
        raise KeyError(f"مفيش ملصق اسمه {name} — شغّل tools/make_stickers.py")
    return Image.open(p).convert("RGBA")


MOVES = ("idle", "hop", "bob", "sway", "spin", "pop_in", "walk_in", "fall", "wobble")


def _smooth(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


class Actor:
    """
    شخصية على الشاشة.
    x, y: موضع المركز (0..1 من مقاس الإطار) · scale: نسبة من ارتفاع الشاشة ·
    move: نوع الحركة · phase: إزاحة زمنية (للتوزيع بين الشخصيات) · flip: الاتجاه ·
    loop: مدة الحلقة (الحركات الدورية بتلف عليها) · enter/exit: وقت الظهور/الاختفاء.
    """

    def __init__(self, who: str, x: float = 0.5, y: float = 0.72, scale: float = 0.32,
                 move: str = "idle", phase: float = 0.0, flip: bool = False,
                 loop: float = 8.0, enter: float | None = None, exit: float | None = None,
                 blink: bool = True, shadow: float = 0.55, tilt: float = 0.0,
                 hue: tuple | None = None):
        if move not in MOVES:
            raise KeyError(f"حركة غير معروفة: {move} (المتاح: {', '.join(MOVES)})")
        self.who, self.x, self.y, self.scale = who, float(x), float(y), float(scale)
        self.move, self.phase, self.flip = move, float(phase), bool(flip)
        self.loop, self.enter, self.exit = float(loop), enter, exit
        self.blink, self.shadow, self.tilt = bool(blink), float(shadow), float(tilt)
        self.hue = hue
        self._img = load_sprite(who)
        self._blink_img = load_sprite(BLINK_PAIRS.get(who, who))
        if hue:
            self._img = _tint(self._img, hue)
            if BLINK_PAIRS.get(who, who) != who:
                self._blink_img = _tint(self._blink_img, hue)

    # ── حركة ──
    def pose(self, t: float) -> dict:
        """يرجّع تحويلات اللحظة: (dx, dy, scale, rot, alpha) بالإحداثيات النسبية."""
        u = (t + self.phase) / max(self.loop, 1e-3)          # دورة دورية
        dx = dy = 0.0
        rot = self.tilt * math.pi / 180.0
        sc, alpha = 1.0, 1.0
        if self.move == "idle":
            dy = -0.006 * math.sin(TAU * u)
            sc = 1.0 + 0.012 * math.sin(TAU * u + 0.6)
            rot += 0.015 * math.sin(TAU * u * 0.5 + 1.0)
        elif self.move == "bob":
            dy = -0.02 * math.sin(TAU * u)
            sc = 1.0 + 0.03 * math.sin(TAU * u * 2.0)
        elif self.move == "hop":
            h = abs(math.sin(TAU * u))                       # قوس نطّ
            dy = -0.10 * h
            sq = 1.0 + 0.10 * math.cos(TAU * u * 2.0)        # انضغاط عند الهبوط
            sc = sc * sq
            rot += 0.06 * math.sin(TAU * u * 2.0)
        elif self.move == "sway":
            dx = 0.03 * math.sin(TAU * u)
            rot += 0.10 * math.sin(TAU * u + 0.4)
        elif self.move == "wobble":
            rot += 0.16 * math.sin(TAU * u * 1.0)
            dx = 0.012 * math.sin(TAU * u * 2.0 + 1.4)
            dy = -0.008 * abs(math.sin(TAU * u * 1.0))
        elif self.move == "spin":
            rot += TAU * u
        elif self.move == "pop_in":
            k = _smooth(min(t / 0.45, 1.0))
            sc = 0.25 + 0.75 * k * (1.0 + 0.18 * math.sin(k * math.pi))
            alpha = k
            dy = -0.06 * (1 - k)
        elif self.move == "walk_in":
            k = _smooth(min(t / 1.1, 1.0))
            dx = -(1.0 - k) * 0.55
            dy = -0.004 * math.sin(TAU * u * 3.0)
            rot += 0.03 * math.sin(TAU * u * 6.0)
        elif self.move == "fall":
            k = _smooth(min(t / 0.6, 1.0))
            dy = -(1.0 - k) * 0.45
            sc = 1.0 + 0.06 * (1 - k)
            rot += 0.25 * (1 - k) * (-1 if self.flip else 1)
        if self.enter is not None:                            # ظهور إجباري
            k = _smooth(min(max((t - self.enter) / 0.4, 0.0), 1.0))
            alpha = min(alpha, k)
        if self.exit is not None:                             # اختفاء
            k = _smooth(min(max((self.exit - t) / 0.4, 0.0), 1.0))
            alpha = min(alpha, k)
        return {"dx": dx, "dy": dy, "scale": sc, "rot": rot, "alpha": max(alpha, 0.0)}

    def blink_state(self, t: float) -> bool:
        """رمشة سريعة كل ~2.6 ثانية (شبه عشوائية لكن مُعطاة ⇒ الحلقة ثابتة)."""
        if not self.blink or BLINK_PAIRS.get(self.who, self.who) == self.who:
            return False
        u = (t + self.phase * 1.7) % 2.6
        return u < 0.12

    def sprite_at(self, t: float) -> Image.Image:
        return self._blink_img if self.blink_state(t) else self._img


def _tint(img: Image.Image, hue: tuple) -> Image.Image:
    """صبغة خفيفة (لتنويع الشخصيات من غير أصول جديدة)."""
    a = np.asarray(img).astype(np.float32) / 255.0
    col = np.array(hue, np.float32)
    a[:, :, :3] = a[:, :, :3] * (1 - 0.35) + a[:, :, :3] * col[None, None, :] * 0.35
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGBA")


class Layer:
    """طبقة الشخصيات فوق مشهد: ظل تلامس + دمج ناعم + إضاءة محيطة."""

    def __init__(self, w: int, h: int, ambient: float = 0.88, shadow_soft: float = 0.55):
        self.w, self.h = int(w), int(h)
        self.actors: list[Actor] = []
        self.ambient = ambient            # الشخصية بتاخد شوية من لون الجو (تندمج)
        self.shadow_soft = shadow_soft
        yy, xx = np.mgrid[0:self.h, 0:self.w]
        self._xx = xx.astype(np.float32)
        self._yy = yy.astype(np.float32)

    def add(self, actor: Actor) -> "Layer":
        self.actors.append(actor)
        return self

    def compose(self, bg: np.ndarray, t: float, ambient_color=(0.6, 0.65, 0.8)) -> np.ndarray:
        """bg: صورة float 0..1 (H,W,3) — بيرجّع **نسخة** بعد إضافة الظلال والشخصيات (مش بيعدّل الأصل)."""
        out = np.array(bg, dtype=np.float32, copy=True)
        amb = np.asarray(ambient_color, np.float32)
        for a in self.actors:
            pose = a.pose(t)
            if pose["alpha"] <= 0.003:
                continue
            side = max(8, int(a.scale * self.h))
            spr = a.sprite_at(t)
            s = side / spr.height
            new_w = max(2, int(spr.width * s * pose["scale"]))
            new_h = max(2, int(spr.height * s * pose["scale"]))
            img = spr.resize((new_w, new_h), Image.LANCZOS)
            if a.flip:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            if abs(pose["rot"]) > 1e-3:
                img = img.rotate(math.degrees(pose["rot"]), resample=Image.BICUBIC,
                                 expand=True, fillcolor=(0, 0, 0, 0))
            cx = int((a.x + pose["dx"]) * self.w)
            cy = int((a.y + pose["dy"]) * self.h)
            x0, y0 = cx - img.width // 2, cy - img.height // 2
            sx0, sy0 = max(0, x0), max(0, y0)
            sx1, sy1 = min(self.w, x0 + img.width), min(self.h, y0 + img.height)
            if sx0 >= sx1 or sy0 >= sy1:
                continue
            patch = img.crop((sx0 - x0, sy0 - y0, sx1 - x0, sy1 - y0))
            pa = np.asarray(patch).astype(np.float32) / 255.0
            alpha = pa[:, :, 3:4] * pose["alpha"]
            rgb = pa[:, :, :3]
            # ظل تلامس بيضاوي (تحت الشخصية، بيتّسع مع الحركة)
            if a.shadow > 0:
                lift = max(0.0, -pose["dy"])
                sw = (sx1 - sx0) * (0.62 - 0.5 * lift)
                sh_y = min(self.h - 1, int(a.y * self.h + a.scale * self.h * 0.06))
                xs = self._xx[sy0:sy1, sx0:sx1]
                ys = self._yy[sy0:sy1, sx0:sx1]
                d = ((xs - cx) / max(sw, 4.0)) ** 2 + ((ys - sh_y) / max(8.0, a.scale * self.h * 0.10)) ** 2
                shadow = np.exp(-d * 2.2) * a.shadow * (1.0 - 0.55 * lift)
                out[sy0:sy1, sx0:sx1] *= (1.0 - 0.55 * shadow[:, :, None])
            # دمج: الشخصية بتاخد لون الجو بشكل خفيف + إضاءة حافة ناعمة
            lit = rgb * self.ambient + (1.0 - self.ambient) * amb[None, None, :] * rgb.mean(axis=2, keepdims=True)
            sub = out[sy0:sy1, sx0:sx1]
            out[sy0:sy1, sx0:sx1] = sub * (1.0 - alpha) + lit * alpha
        return out
