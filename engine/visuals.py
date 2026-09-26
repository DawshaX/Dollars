"""
🎬 محرّك المشاهد الحيّة — Dollars Studio
========================================
كل حاجة هنا **متولّدة بالكود**: ملكية كاملة 100%، صفر حقوق، صفر سرقة.

المبادئ:
- كل مشهد دالة **دورية** في الزمن (loop_seconds) ⇒ حلقة مثالية بلا أي قطع.
- الحركة حقيقية: جزيئات · موجات · سُحب · لهب · كاميرا بتتحرك · أحداث بتحصل
  (شهب · برق · راكة رمل · كور بتتحرك) — مش صورة ثابتة.
- فيديو 10 ساعات = نعمل الحلقة *مرة واحدة* ثم ffmpeg يكرّرها بـ copy
  (بلا إعادة ترميز) ⇒ سريع جدًا وبلا استهلاك رام.

الواجهة:
    scene = make_scene("rain_glass")
    encode(scene, seconds=120, path="out/loop.mp4")
    long_video("out/loop.mp4", out="out/10h.mp4", total_seconds=36000, audio_wav="rain.wav")
"""
from __future__ import annotations

import math
import pathlib
import subprocess

import numpy as np

try:  # ffmpeg من imageio (مفيش ffmpeg نظام على البيئة دي)
    from imageio_ffmpeg import get_ffmpeg_exe

    FFMPEG = get_ffmpeg_exe()
except Exception:  # pragma: no cover
    FFMPEG = "ffmpeg"

from .proc import (TAU, blur, fbm, tiled_fbm, tiled_fbm2, pick_period, roll_px,
                     splat, splat_fast, glow, smoothstep, _mix, _bilerp, FFMPEG)
from . import grade as _grade

# 🎞️ المظهر الافتراضي لكل مشهد (طقم الجودة السينمائي) — يتغيّر من مكان واحد
LOOKS = {
    "rain_glass": "cinema_night", "ocean": "cinema_cool", "fireplace": "cinema_warm",
    "starfield": "cinema_night", "aurora": "cinema_cool",
    "sand_table": "satisfying", "pendulum_wave": "satisfying", "harmonograph": "satisfying",
    "black_screen": "cinema_night",
    "valley_lake": "cinema_cool", "dunes_moon": "cinema_warm", "snow_pines": "cinema_warm",
    "planet_rings": "cinema_night",
}

# ────────────────────────────── القاعدة ──────────────────────────────

class Scene:
    """مشهد دوري: frame(t + loop_seconds) ≈ frame(t)."""
    name = "scene"
    loop_seconds = 60.0
    stateful = False
    grain_amp = 0.012

    def __init__(self, w: int = 1280, h: int = 720, fps: int = 30, seed: int = 7):
        self.w, self.h, self.fps, self.seed = int(w), int(h), int(fps), int(seed)
        yy, xx = np.mgrid[0:h, 0:w]
        self.xx = xx.astype(np.float32); self.yy = yy.astype(np.float32)
        dx = (xx / max(1, w - 1) - 0.5) * 2.0; dy = (yy / max(1, h - 1) - 0.5) * 2.0
        self.vig = np.clip(1.0 - 0.28 * (dx * dx + dy * dy) ** 1.25, 0.55, 1.0).astype(np.float32)
        g = np.random.default_rng(seed + 991).random((24, h // 3 + 1, w // 3 + 1), dtype=np.float32)
        self.grain = np.ascontiguousarray(g, dtype=np.float32)
        self.prepare()

    def prepare(self) -> None:  # pragma: no cover
        pass

    def reset(self) -> None:
        """للمشاهد ذات الحالة."""

    def render(self, t: float) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def raw(self, t: float) -> np.ndarray:
        """المشهد قبل الحبيبات والفينييت (للاختبارات والتحليل)."""
        return self.render(float(t))

    def frame(self, t: float, index: int | None = None) -> np.ndarray:
        img = self.raw(t)
        i = int(index if index is not None else round(t * self.fps))
        g = self.grain[i % self.grain.shape[0]]
        g = np.repeat(np.repeat(g, 3, axis=0), 3, axis=1)[:self.h, :self.w]
        img += (g - 0.5)[:, :, None] * (self.grain_amp * 2.0)
        img *= self.vig[:, :, None]
        return (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


# ────────────────────────────── 1) سماء النجوم ──────────────────────────────

class Starfield(Scene):
    """فضاء حيّ: نجوم بتلمع · سُحب مجرّية بتزحف · شهب · تنفّس هادي."""
    name = "starfield"
    loop_seconds = 60.0

    def prepare(self):
        h, w, sd = self.h, self.w, self.seed
        self.p1 = pick_period(w, w // 4)
        self.p2 = pick_period(w, w // 6)
        self.neb = blur(tiled_fbm(h, w, sd + 1, self.p1, scales=(4, 8, 16, 32, 64), gain=0.58), 1.5)
        self.neb2 = blur(tiled_fbm(h, w, sd + 2, self.p2, scales=(8, 16, 32, 64), gain=0.6), 1.0)
        rng = np.random.default_rng(sd + 3)
        self.tw = pick_period(w, max(64, w // 3))
        self.th = pick_period(h, max(64, h // 2))
        self.xoff = np.arange(0, w, self.tw, dtype=np.float32)
        self.yoff = np.arange(0, h, self.th, dtype=np.float32)
        self.layers = []
        for n, kb, bright in ((190, 2, 1.0), (110, 3, 0.70), (60, 5, 0.50)):
            kx = rng.integers(1, 3, n).astype(np.float32)
            ky = rng.integers(1, 3, n).astype(np.float32)
            self.layers.append(dict(
                x=rng.random(n, dtype=np.float32) * self.tw,
                y=rng.random(n, dtype=np.float32) * self.th,
                b=(0.4 + 0.6 * rng.random(n, dtype=np.float32)) * bright,
                f=rng.integers(1, 5, n), p=rng.random(n, dtype=np.float32) * TAU,
                vx=kx * self.tw / self.loop_seconds, vy=ky * self.th / self.loop_seconds))

    def render(self, t):
        h, w, L = self.h, self.w, self.loop_seconds
        u = t / L
        img = np.zeros((h, w, 3), np.float32)
        n1 = roll_px(self.neb, self.p1 * u)
        n2 = roll_px(self.neb2, -self.p2 * u)
        deep = np.array([0.010, 0.016, 0.042], np.float32)
        purple = np.array([0.17, 0.075, 0.31], np.float32)
        teal = np.array([0.03, 0.17, 0.23], np.float32)
        img += deep * (1.0 - n1[:, :, None] * 0.5)
        img += purple * (n1 * n2)[:, :, None] * 0.55
        img += teal * (n2 ** 1.6)[:, :, None] * 0.30
        # درب التبانة: شريط ضبابي ناعم يميل عبر الكادر
        band = np.exp(-(((self.yy - (h * 0.42 + 0.16 * h * np.sin(self.xx / (w * 0.55)))) / (h * 0.11)) ** 2))
        img += (band * (0.05 + 0.10 * n2))[:, :, None] * np.array([0.55, 0.62, 0.95], np.float32)
        for lay in self.layers:
            nx = np.mod(lay["x"] + lay["vx"] * t, self.tw)
            ny = np.mod(lay["y"] + lay["vy"] * t, self.th)
            twk = 0.55 + 0.45 * np.sin(TAU * (lay["f"] * u) + lay["p"])
            br = (lay["b"] * twk * 0.72)[:, None, None] * np.ones((1, self.xoff.size, self.yoff.size), np.float32)
            xs = (nx[:, None, None] + self.xoff[None, :, None])
            ys = (ny[:, None, None] + self.yoff[None, None, :])
            xs = np.broadcast_to(xs, br.shape); ys = np.broadcast_to(ys, br.shape)
            splat_fast(img, np.ascontiguousarray(xs).ravel(), np.ascontiguousarray(ys).ravel(),
                       br.ravel(), (0.95, 0.96, 1.0))
        for ev in (0.0, 0.5):
            uu = ((u - ev) % 1.0) * L / 1.6
            if uu < 1.0:
                k = np.linspace(0.0, 1.0, 30, dtype=np.float32)
                ax = w * (0.12 + 0.5 * ev) + k * w * 0.44
                ay = h * (0.16 + 0.34 * ev) + k * h * 0.26
                br = np.exp(-k * 5.0) * max(0.0, 1.0 - uu) * 1.6
                splat_fast(img, ax, ay, br, (1.0, 0.95, 0.85))
        return img


# ────────────────────────────── 2) مطر على الزجاج ──────────────────────────────

class RainGlass(Scene):
    """ليل + مطر على زجاج: خطوط بتمشي · قطرات بتزحلق · برق · بوكيه أضواء."""
    name = "rain_glass"
    loop_seconds = 60.0

    def prepare(self):
        h, w, sd, L = self.h, self.w, self.seed, self.loop_seconds
        rng = np.random.default_rng(sd + 11)
        self.city = tiled_fbm(h, w, sd + 12, pick_period(w, w // 5), scales=(8, 16, 32, 64), gain=0.6)
        self.pc = pick_period(w, w // 5)
        self.lights = [(float(rng.random() * w), float(h * (0.55 + 0.42 * rng.random())),
                        float(rng.uniform(22, 62)), float(rng.uniform(0.22, 0.62)),
                        rng.choice([np.array([1.0, 0.72, 0.35], np.float32),
                                    np.array([0.45, 0.75, 1.0], np.float32),
                                    np.array([1.0, 0.95, 0.85], np.float32)]))
                       for _ in range(26)]
        n = 300
        self.rx = rng.random(n, dtype=np.float32) * w
        self.ry = rng.random(n, dtype=np.float32) * (h + 240)
        self.rlen = rng.uniform(22, 78, n).astype(np.float32)
        # سرعة المطر = عدد صحيح من ارتفاعات الشاشة لكل حلقة ⇒ حلقة مثالية
        self.rsp = (rng.integers(2, 7, n).astype(np.float32) * (h + 240) / L)
        self.ra = rng.uniform(0.10, 0.30, n).astype(np.float32)
        m = 64
        self.dx = rng.random(m, dtype=np.float32) * w
        self.dy = rng.random(m, dtype=np.float32) * h * 0.9
        self.dr = rng.uniform(2.6, 7.5, m).astype(np.float32)
        self.dp = rng.random(m, dtype=np.float32)
        self.dsl = rng.uniform(0.25, 1.0, m).astype(np.float32)
        self.dn = rng.integers(1, 3, m)
        self.flash_t = [0.28, 0.66]
        self.flash2_t = [0.31, 0.685]
        self.seg = np.linspace(0.0, 1.0, 9, dtype=np.float32)

    def render(self, t):
        h, w, L = self.h, self.w, self.loop_seconds
        u = t / L
        img = np.zeros((h, w, 3), np.float32)
        sky = np.array([0.035, 0.045, 0.075], np.float32)
        city = roll_px(self.city, self.pc * u)
        img += sky * (0.7 + 0.6 * city[:, :, None])
        for (lx, ly, lr, lb, lc) in self.lights:
            x = lx + 26.0 * math.sin(TAU * u + lx * 0.01)
            glow(img, x, ly, lr * (1.0 + 0.12 * math.sin(TAU * 2 * u + ly * 0.02)), lc, lb * 0.5, 2.0)
        base = img.copy()
        y = np.mod(self.ry + self.rsp * t, h + 240) - 120
        for k in range(0, len(self.rx), 75):     # تجميع الخطوط في دفعات (سرعة)
            sel = slice(k, k + 75)
            ln = self.rlen[sel][:, None] * self.seg[None, :]
            ys = (y[sel][:, None] - ln).ravel()
            xs = (self.rx[sel][:, None] + 6.0 * self.seg[None, :]).ravel()
            br = (self.ra[sel][:, None] * np.linspace(1.0, 0.15, len(self.seg), dtype=np.float32)[None, :]).ravel()
            splat_fast(img, xs, ys, br, (0.72, 0.80, 0.95))
        prog = np.mod(u * self.dn + self.dp, 1.0)
        slide = smoothstep(np.clip((prog - 0.35) / 0.6, 0.0, 1.0))
        radius = self.dr * (0.55 + 0.75 * smoothstep(np.clip(prog / 0.35, 0.0, 1.0)))
        dy = self.dy + slide * self.dsl * self.dr * 4.0
        fade = np.clip(np.minimum(prog / 0.12, (1.0 - prog) / 0.18), 0.0, 1.0)
        for j in range(len(self.dx)):
            py, px, pr, k = float(dy[j]), float(self.dx[j]), float(radius[j]), float(fade[j])
            if k <= 0.02:
                continue
            y0, y1 = max(0, int(py - pr)), min(h, int(py + pr) + 1)
            x0, x1 = max(0, int(px - pr)), min(w, int(px + pr) + 1)
            if y0 >= y1 or x0 >= x1:
                continue
            sub = img[y0:y1, x0:x1]
            xs = np.arange(x0, x1, dtype=np.float32)[None, :] - np.float32(px)
            ys = np.arange(y0, y1, dtype=np.float32)[:, None] - np.float32(py)
            d = np.sqrt(xs * xs + ys * ys) / max(pr, 1e-6)
            rim = np.exp(-((d - 0.86) ** 2) * 26.0)
            lens = np.exp(-(d ** 2) * 2.4)
            for c in range(3):
                sub[:, :, c] += rim * (0.12 * k) + lens * (0.025 * k)
                sub[:, :, c] += lens * base[y0:y1, x0:x1, c] * (0.5 * k)
        flash = 0.0
        for ft in self.flash_t:
            d1 = ((u - ft) % 1.0) * L
            flash += math.exp(-(d1 * 3.2) ** 2)
        for ft in self.flash2_t:
            d1 = ((u - ft) % 1.0) * L
            flash += 0.45 * math.exp(-(d1 * 7.0) ** 2)
        img += (0.16 * flash) * np.array([0.75, 0.80, 1.0], np.float32)
        return img


# ────────────────────────────── 3) بحر وموج ──────────────────────────────

class Ocean(Scene):
    """بحر حيّ: موج بيتمشى · رغوة · قمر وانعكاسه · سُحب بتزحف."""
    name = "ocean"
    loop_seconds = 60.0

    def prepare(self):
        h, w, sd = self.h, self.w, self.seed
        self.pc = pick_period(w, w // 6)
        self.pf = pick_period(w, w // 8)
        self.sky = tiled_fbm(h, w, sd + 21, self.pc, scales=(16, 32, 64, 128), gain=0.6)
        self.foam = tiled_fbm(h, w, sd + 22, self.pf, scales=(4, 8, 16, 32), gain=0.62)
        self.horizon = int(h * 0.46)
        self.moon_x = w * 0.68
        self.moon_y = h * 0.19

    def render(self, t):
        h, w, L = self.h, self.w, self.loop_seconds
        u = t / L
        img = np.zeros((h, w, 3), np.float32)
        top = np.array([0.020, 0.032, 0.070], np.float32)
        bot = np.array([0.075, 0.085, 0.130], np.float32)
        ramp = np.clip((self.yy / max(1, self.horizon))[:, :, None], 0, 1)
        img += _mix(top, bot, ramp)
        cloud = roll_px(self.sky, self.pc * u)
        img[:self.horizon] += cloud[:self.horizon, :, None] * 0.10
        glow(img, self.moon_x, self.moon_y, 210, (0.85, 0.90, 1.0), 0.30, 2.0)
        glow(img, self.moon_x, self.moon_y, 46, (1.0, 1.0, 0.98), 0.55, 2.4)
        yy = np.clip(self.yy - self.horizon, 0, None)
        depth = yy / max(1.0, (h - self.horizon))
        img += np.array([0.015, 0.030, 0.060], np.float32) * (1.0 - 0.4 * depth[:, :, None])
        for i, (amp, lam, spd, shade) in enumerate([
                (0.55, 520.0, 1, 0.055), (0.40, 310.0, 2, 0.075),
                (0.28, 175.0, 4, 0.10), (0.18, 105.0, 7, 0.085)]):
            ph = TAU * (self.xx / lam + spd * u)
            band = amp * np.sin(ph + depth * (5.0 + 3.0 * i))
            band = band * (0.25 + 0.75 * depth)
            img += shade * band[:, :, None] * np.array([0.55, 0.75, 1.0], np.float32)
            crest = np.clip(band - amp * 0.55, 0.0, None)
            f = roll_px(self.foam, self.pf * spd * u)
            mask = crest[:h, :] * (0.5 + 0.9 * depth)
            img += (f * mask)[:, :, None] * 0.30
        rx = (self.xx - self.moon_x)
        col = np.exp(-(rx / 62.0) ** 2) * (self.yy > self.horizon)
        flick = 0.6 + 0.4 * np.sin(TAU * 3 * u + self.yy * 0.35) * np.sin(TAU * 2 * u)
        img += (col * flick * 0.20)[:, :, None] * np.array([0.9, 0.94, 1.0], np.float32)
        return img


# ────────────────────────────── 4) الشفق القطبي ──────────────────────────────

class Aurora(Scene):
    """شفق قطبي حيّ: ستائر بتراقص · نجوم · جبل · ضباب."""
    name = "aurora"
    loop_seconds = 60.0

    def prepare(self):
        h, w, sd = self.h, self.w, self.seed
        self.star_bg = Starfield(w=w, h=h, seed=sd + 31)
        self.curtain = tiled_fbm(h, w, sd + 32, pick_period(w, w // 3), scales=(4, 8, 16, 32), gain=0.55)
        self.curtain = blur(self.curtain, 2.4)
        self.curtain = np.clip((self.curtain - 0.28) / 0.62, 0.0, 1.0)
        self.pc = pick_period(w, w // 3)
        self.mist = blur(tiled_fbm(h, w, sd + 33, pick_period(w, w // 6), scales=(8, 16, 32), gain=0.6), 2.0)
        self.pm = pick_period(w, w // 6)
        self.curve = (h * 0.80 + 0.05 * h * np.sin(self.xx / 190.0)
                      + 0.03 * h * np.sin(self.xx / 61.0 + 1.7))
        self.mask_mtn = (self.yy > self.curve).astype(np.float32)

    def render(self, t):
        h, w, L = self.h, self.w, self.loop_seconds
        u = t / L
        img = self.star_bg.render(t) * 0.80
        for k, (y0f, amp, lam, col, pw) in enumerate([
                (0.30, 0.10, 420.0, np.array([0.10, 0.85, 0.45], np.float32), 0.75),
                (0.42, 0.13, 300.0, np.array([0.15, 0.75, 0.85], np.float32), 0.55),
                (0.56, 0.09, 520.0, np.array([0.45, 0.25, 0.95], np.float32), 0.35)]):
            tex = roll_px(self.curtain, self.pc * (k + 1) * u)
            centre = h * y0f + h * amp * np.sin(TAU * ((k + 1) * u) + self.xx / lam)
            width = h * (0.075 + 0.02 * math.sin(TAU * 2 * u + k))
            band = np.exp(-(((self.yy - centre) / width) ** 2))
            img += (band * (0.42 + 0.85 * tex) * pw)[:, :, None] * col
        mist = roll_px(self.mist, self.pm * u)
        img += (mist * 0.05)[:, :, None]
        m = self.mask_mtn[:, :, None]
        img = img * (1.0 - m) + m * 0.015
        img += (mist * self.mask_mtn * 0.05)[:, :, None]
        return img


# ────────────────────────────── 5) مدفأة ──────────────────────────────

class Fireplace(Scene):
    """نار حيّة: لهب · جمر طائر · جذوع · رفرفة ضوء على الحجر."""
    name = "fireplace"
    loop_seconds = 60.0
    grain_amp = 0.02

    def prepare(self):
        h, w, sd, L = self.h, self.w, self.seed, self.loop_seconds
        rng = np.random.default_rng(sd + 41)
        self.stone = tiled_fbm(h, w, sd + 42, pick_period(w, w // 4), scales=(8, 16, 32, 64), gain=0.6)
        self.ps = pick_period(w, w // 4)
        self.pfl_y = pick_period(h, h // 4)
        self.pfl_x = pick_period(w, w // 5)
        self.flame_tex = tiled_fbm2(h, w, sd + 43, self.pfl_y, self.pfl_x,
                                    scales=(4, 8, 16, 32), gain=0.65)
        self.fire_base = h * 0.80
        self.fire_cx = w * 0.5
        n = 110
        self.ex = self.fire_cx + rng.uniform(-0.16, 0.16, n) * w
        self.ey = rng.random(n, dtype=np.float32) * h * 0.42
        self.ev = rng.integers(1, 4, n).astype(np.float32) * (h * 0.42) / L
        self.ep = rng.random(n, dtype=np.float32) * TAU
        self.es = rng.uniform(0.6, 1.8, n).astype(np.float32)
        self.efreq = rng.integers(1, 4, n)
        # إطار حجري ناعم: أقواس في الأعلى وحواف مخفّفة (شكل مدفأة مش صندوق)
        u = self.xx / max(1, w - 1)
        v = self.yy / max(1, h - 1)
        arch = 0.055 + 0.075 * (0.5 - 0.5 * np.cos(np.pi * np.clip((v - 0.02) / 0.55, 0, 1)))
        edge = np.clip((arch - u) / 0.035, 0, 1) + np.clip((u - (1.0 - arch)) / 0.035, 0, 1)
        top = np.clip((0.115 + 0.055 * np.cos(np.pi * np.clip(u, 0, 1)) - v) / 0.05, 0, 1)
        self.frame_mask = np.clip(edge + top, 0.0, 1.0).astype(np.float32)
        self.logs = [(w * 0.34, h * 0.815, w * 0.30), (w * 0.60, h * 0.835, w * 0.26),
                     (w * 0.47, h * 0.775, w * 0.20)]

    def render(self, t):
        h, w, L = self.h, self.w, self.loop_seconds
        u = t / L
        flick = (0.80 + 0.10 * math.sin(TAU * 3 * u) + 0.06 * math.sin(TAU * 7 * u + 1.1)
                 + 0.04 * math.sin(TAU * 13 * u + 2.3))
        img = np.zeros((h, w, 3), np.float32)
        stone = roll_px(self.stone, self.ps * u * 0.0)
        heat_wall = np.exp(-(((self.xx - self.fire_cx) / (w * 0.34)) ** 2))
        img += (stone * 0.05 * flick + heat_wall * 0.030 * flick)[:, :, None] * np.array([1.0, 0.74, 0.48], np.float32)
        tex = np.roll(np.roll(self.flame_tex, int(round(self.pfl_y * 2 * u)), axis=0),
                      int(round(self.pfl_x * u)), axis=1)
        # ── لهب حقيقي: ألسنة متعددة بتتراقص، قاعدة ساخنة بيضاء والطرف أحمر خفيف
        up = np.clip((self.fire_base - self.yy) / (h * 0.47), 0.0, 1.0)
        tongues = np.zeros((h, w), np.float32)
        for ox, wf, ph, sp in ((-0.62, 0.9, 0.0, 3.0), (-0.18, 1.15, 0.35, 4.0),
                               (0.30, 1.0, 0.62, 3.0), (0.66, 0.8, 0.85, 2.0)):   # سرعات صحيحة = حلقة مثالية
            wob = 0.045 * w * math.sin(TAU * sp * u + ph) + 0.02 * w * math.sin(TAU * 7.0 * u + ph * 2)
            dx = (self.xx - (self.fire_cx + ox * w * 0.085 + wob)) / (w * 0.085 * wf)
            taper = np.clip(1.0 - up * (0.85 + 0.25 * math.sin(TAU * 2.0 * u + ph)), 0.0, 1.0) ** 1.35
            tongues += np.exp(-(dx ** 2) * 2.1) * taper * (0.75 + 0.5 * math.sin(TAU * 3.0 * u + ph))
        # جمر القاعدة: محدود حوالين النار + مكسّر بالنسيج (مش شريط)
        spread = np.exp(-(((self.xx - self.fire_cx) / (w * 0.17)) ** 2))
        coals = (np.exp(-(((self.yy - self.fire_base) / (h * 0.048)) ** 2)) * spread
                 * (0.25 + 0.95 * self.stone))
        heat = np.clip(tongues * (0.40 + 1.15 * tex) * 1.25 + coals * (0.55 + 0.9 * tex), 0.0, 1.35)
        heat *= np.clip((self.fire_base - self.yy) / 7.0 + 1.0, 0.0, 1.0)
        r = np.clip(heat * 1.30, 0, 1)
        g = np.clip((heat - 0.22) * 1.22, 0, 1) ** 1.12
        b = np.clip((heat - 0.72) * 1.10, 0, 1) ** 1.7
        field = heat
        img += np.stack([r, g, b], axis=2) * flick * 1.05
        glow(img, self.fire_cx, self.fire_base - h * 0.10, w * 0.34, (1.0, 0.46, 0.14), 0.30 * flick, 2.0)
        ey = self.fire_base - np.mod(self.ev * t + self.ey, h * 0.42)
        ex = self.ex + 8.0 * np.sin(TAU * (self.efreq * u) + self.ep)
        tw = 0.5 + 0.5 * np.sin(TAU * (self.efreq * 2 * u) + self.ep)
        splat_fast(img, ex, ey, 0.55 * self.es * tw, (1.0, 0.55, 0.18), wrap=False)
        for (lx, ly, lw) in self.logs:
            y0, y1 = int(ly - h * 0.035), int(ly + h * 0.030)
            x0, x1 = int(lx - lw / 2), int(lx + lw / 2)
            xs = np.arange(x0, x1, dtype=np.float32)[None, :]
            ell = np.sqrt(np.clip(1.0 - ((xs - (x0 + x1) / 2) / (lw / 2)) ** 2, 0, 1))
            t01 = np.linspace(0, 1, max(1, y1 - y0), dtype=np.float32)[:, None]
            band = np.clip(ell * (0.65 - np.abs(t01 - 0.45) * 1.1), 0, 1)
            band = band * (0.55 + 0.45 * self.stone[y0:y1, x0:x1])
            img[y0:y1, x0:x1] += band[:, :, None] * np.array([0.20, 0.115, 0.070], np.float32)
            img[y0:y1, x0:x1] += (band * field[y0:y1, x0:x1])[:, :, None] * np.array(
                [0.45, 0.16, 0.03], np.float32)
        fm = self.frame_mask[:, :, None]
        img = img * (1 - fm) + fm * (0.10 + 0.10 * self.stone[:, :, None]) * np.array(
            [0.95, 0.82, 0.70], np.float32)
        img += fm * (0.16 * flick) * np.array([0.7, 0.42, 0.20], np.float32)
        return img


# ────────────────────────────── 6) طاولة الرمل (مريح للعين) ──────────────────────────────

class SandTable(Scene):
    """
    رمل حركي من فوق: كورة مصقولة بتحفر خطوط في رمل أسود ناعم —
    الضوء جاي من فوق شمال، فالجُرف بيبان بلمعة على حرف والحفر بظل على الحرف التاني.
    آخر الحلقة «راكة» بتمسح السطح بالكامل ⇒ الحلقة مثالية (نفس الكادر بالظبط).
    """
    name = "sand_table"
    loop_seconds = 40.0
    stateful = True

    def prepare(self):
        h, w, sd = self.h, self.w, self.seed
        self.sand_tex = fbm(h, w, sd + 51, scales=(3, 6, 12, 24, 48), gain=0.62)          # نسيج الرمل
        self.fine = fbm(h, w, sd + 52, scales=(48, 96, 192), gain=0.55)                    # حبيبات دقيقة
        self.cx, self.cy = w * 0.5, h * 0.5
        self.R = min(w, h) * 0.34
        self.ball_r = max(3.0, min(w, h) * 0.035)
        self.draw_until = 0.80
        self.reset()

    def reset(self):
        self.carve = np.zeros((self.h, self.w), np.float32)      # عمق الحفر
        self.ridge = np.zeros((self.h, self.w), np.float32)      # كومات رمل على الجناب
        self.last = None

    def _pos(self, u):
        """مسار لِيساجو ناعم بيرجع لنفس النقطة (حلقة مقفولة)."""
        a = TAU * u
        x = self.cx + self.R * (0.70 * math.sin(3 * a) + 0.22 * math.sin(5 * a + 0.7))
        y = self.cy + self.R * 0.82 * (0.70 * math.cos(2 * a) + 0.26 * math.cos(7 * a + 1.2))
        return x, y

    def _carve(self, x0, y0, x1, y1):
        h, w = self.h, self.w
        steps = max(2, int(math.hypot(x1 - x0, y1 - y0) * 1.6))
        br = max(3.0, self.ball_r * 0.55)
        for i in range(1, steps + 1):
            xi = x0 + (x1 - x0) * i / steps
            yi = y0 + (y1 - y0) * i / steps
            px, py = int(round(xi)), int(round(yi))
            r = int(br) + 1
            if px < r or py < r or px >= w - r or py >= h - r:
                continue
            yy, xx = np.mgrid[py - r:py + r + 1, px - r:px + r + 1]
            d = np.sqrt((xx - xi) ** 2 + (yy - yi) ** 2)
            self.carve[py - r:py + r + 1, px - r:px + r + 1] += np.exp(-(d / br) ** 2) * 1.6
            self.ridge[py - r:py + r + 1, px - r:px + r + 1] += np.exp(-((d - br * 1.5) / (br * 0.9)) ** 2) * 0.9

    def render(self, t):
        h, w, L = self.h, self.w, self.loop_seconds
        u = (t % L) / L
        if t < 1.0 / self.fps:
            self.reset()
        drawing = u <= self.draw_until
        clean = 0.0 if drawing else smoothstep((u - self.draw_until) / (1.0 - self.draw_until))
        if drawing:
            x, y = self._pos(u / self.draw_until)
            if self.last:
                self._carve(self.last[0], self.last[1], x, y)
            self.last = (x, y)
        np.clip(self.carve, 0.0, 6.0, out=self.carve)
        np.clip(self.ridge, 0.0, 4.0, out=self.ridge)
        if not drawing:                                   # الراكة بتمسح الحفر والكومات
            self.carve *= (1.0 - 0.20 * (1.0 - clean))
            self.ridge *= (1.0 - 0.20 * (1.0 - clean))
        # ── إضاءة: مصدر ضوء واحد من فوق-شمال ⇒ كل حفر له وجه مضيء وحرف مظلّل
        gx = np.zeros_like(self.carve); gy = np.zeros_like(self.carve)
        gx[:, 1:-1] = (self.carve[:, 2:] - self.carve[:, :-2]) * 0.5
        gy[1:-1, :] = (self.carve[2:, :] - self.carve[:-2, :]) * 0.5
        shade = np.clip(-gx * 1.05 - gy * 1.35, -1.0, 1.0)
        worn = np.clip(self.carve * 0.30 + self.ridge * 0.28, 0.0, 1.0)
        base = 0.155 + 0.075 * self.sand_tex + 0.045 * self.fine
        base = base + shade * 0.30 + worn * 0.085
        sand_col = np.array([0.74, 0.70, 0.63], np.float32)      # رمل رمادي-دافئ
        img = (base[:, :, None] * sand_col) * (1.0 - 0.30 * (1.0 - self.vig)[:, :, None])
        img += (self.ridge * 0.035)[:, :, None] * np.array([0.95, 0.90, 0.80], np.float32)
        # ── الكورة: معدن مصقول + ظل ناعم + لمعة
        bx, by = self._pos(u / self.draw_until if drawing else 0.0)
        if not drawing and clean > 0:
            bx = bx * (1 - clean) + w * 0.5 * clean
            by = by * (1 - clean) + h * 0.5 * clean
        r = self.ball_r
        glow(img, bx + r * 0.45, by + r * 0.55, r * 2.6, (0.0, 0.0, 0.0), 0.55, 2.0)      # ظل
        glow(img, bx, by, r * 1.25, (0.62, 0.60, 0.58), 0.55, 3.0)                          # جسم الكورة
        glow(img, bx - r * 0.35, by - r * 0.45, r * 0.75, (1.0, 0.99, 0.96), 0.95, 3.4)     # اللمعة
        glow(img, bx + r * 0.30, by + r * 0.35, r * 0.55, (1.0, 0.97, 0.92), 0.30, 3.0)     # انعكاس أرضي
        # ── نهاية الحلقة: ضوء الراكة بيمرّ على السطح ويكمّل المسح
        if not drawing:
            sweep = (u - self.draw_until) / (1.0 - self.draw_until)
            sx = w * (-0.05 + 1.15 * sweep)
            band = np.exp(-(((self.xx - sx) / (w * 0.045)) ** 2))
            img += (band * 0.11)[:, :, None] * np.array([0.95, 0.90, 0.82], np.float32)
        return np.clip(img, 0.0, 1.4)


# ────────────────────────────── 7) موجة النواسير ──────────────────────────────

class PendulumWave(Scene):
    """موجة نواسير في استوديو: 16 كورة مصقولة بتكشف أنماط رياضية مبهِرة على خلفية هادية."""
    name = "pendulum_wave"
    loop_seconds = 45.0

    def __init__(self, w=1280, h=720, fps=30, seed=7, n=16):
        self.n_req = n
        super().__init__(w, h, fps, seed)

    def prepare(self):
        h, w, n = self.h, self.w, self.n_req
        self.pivot_y = h * 0.10
        self.len = h * 0.70
        self.x = np.linspace(w * 0.09, w * 0.91, n, dtype=np.float32)
        self.freq = np.arange(13, 13 + n, dtype=np.float32)
        self.amp = (0.34 + 0.05 * np.sin(np.arange(n) * 1.7)).astype(np.float32)
        self.rad = float(np.clip(min(w, h) * 0.045, 8.0, 26.0))
        self.hue = np.arange(n, dtype=np.float32) / n
        self.cols = np.stack([0.45 + 0.55 * np.sin(TAU * self.hue),
                              0.45 + 0.55 * np.sin(TAU * self.hue + 2.1),
                              0.45 + 0.55 * np.sin(TAU * self.hue + 4.2)], axis=1).astype(np.float32)
        self.horizon = h * 0.80

    def render(self, t):
        h, w, L, n = self.h, self.w, self.loop_seconds, self.n_req
        u = t / L
        img = np.zeros((h, w, 3), np.float32)
        # خلفية استوديو: تدرّج هادي + «أرضية» أنعم
        grad = np.clip(self.yy / max(1, h - 1), 0.0, 1.0)
        img += (0.030 + 0.055 * grad)[:, :, None] * np.array([0.55, 0.63, 0.85], np.float32)
        img += np.clip(1.0 - np.abs(self.yy - self.horizon) / (h * 0.035), 0, 1)[:, :, None] * 0.045
        img *= self.vig[:, :, None]
        # عارضة معدنية مصقولة (خط لمعة فوق · جسم · ظل تحتها)
        y0 = int(self.pivot_y)
        i0, i1 = int(w * 0.055), int(w * 0.945)
        img[max(0, y0 - 5):y0 - 2, i0:i1] += 0.085
        img[max(0, y0 - 2):y0 + 3, i0:i1] += 0.135
        img[y0 + 3:y0 + 6, i0:i1] += 0.045
        th = self.amp * np.cos(TAU * self.freq * u)
        bx = self.x + self.len * np.sin(th)
        by = self.pivot_y + self.len * np.cos(th)
        # خيوط واضحة (سماكة بكسلين بلون فاتح)
        k = np.linspace(0.0, 1.0, 90, dtype=np.float32)
        rxs = self.x[:, None] + (bx - self.x)[:, None] * k[None, :]
        rys = self.pivot_y + (by - self.pivot_y)[:, None] * k[None, :]
        rbr = (0.075 * (0.45 + 0.55 * k))[None, :] * np.ones((n, 1), np.float32)
        splat_fast(img, rxs.ravel(), rys.ravel(), rbr.ravel(), (0.88, 0.92, 1.0))
        splat_fast(img, (rxs + 0.8).ravel(), rys.ravel(), (rbr * 0.6).ravel(), (0.82, 0.88, 0.99))
        # محاور صغيرة على العارضة
        splat_fast(img, self.x, np.full(n, self.pivot_y, np.float32) - 1.0,
                   np.full(n, 0.5, np.float32), (0.95, 0.96, 1.0))
        # انعكاس أرضي باهت + ظل + كرات مصقولة
        for i in range(n):
            gy = self.horizon + (self.len * 0.05) * (1.0 - abs(math.cos(th[i])))
            glow(img, float(bx[i]), float(gy), self.rad * 1.3, (0.0, 0.0, 0.0), 0.30, 2.0)
            c = tuple(float(v) for v in np.clip(self.cols[i] * 0.5 + 0.22, 0.0, 1.0))
            glow(img, float(bx[i]), float(self.horizon + (by[i] - self.pivot_y) * 0.12),
                 self.rad * 0.9, c, 0.10, 2.4)                                               # انعكاس
        for i in range(n):
            c = tuple(float(v) for v in np.clip(self.cols[i] * 0.55 + 0.25, 0.0, 1.0))
            glow(img, float(bx[i]), float(by[i]), self.rad * 1.35, c, 0.38, 3.0)            # جسم الكورة
            glow(img, float(bx[i]) - self.rad * 0.30, float(by[i]) - self.rad * 0.36,
                 self.rad * 0.42, (1.0, 1.0, 1.0), 0.95, 3.4)                               # لمعة
            glow(img, float(bx[i]) + self.rad * 0.22, float(by[i]) + self.rad * 0.30,
                 self.rad * 0.30, (0.9, 0.88, 0.85), 0.25, 3.0)                             # انعكاس أرضي
        return np.clip(img, 0.0, 1.4)


# ────────────────────────────── 8) هارمونوغراف (رسم ضوئي) ──────────────────────────────

class Harmonograph(Scene):
    """هارمونوغراف على ورق: منحنى رياضي بيترسم قدام عينك بالحبر — حرفة يدوية حقيقية."""
    name = "harmonograph"
    loop_seconds = 30.0

    def prepare(self):
        h, w = self.h, self.w
        self.A = h * 0.34
        n = 1400
        self.tt = np.linspace(0.0, 1.0, n, dtype=np.float32)
        self.u0 = np.linspace(0.0, 1.0, n, dtype=np.float32)
        self.span = 0.60
        self.uu = np.mod(self.u0 + (1.0 - self.span), 1.0)
        self.xs, self.ys = self._curve(self.uu)
        self.br = (0.35 + 0.65 * self.tt) * 0.42
        self.paper = fbm(h, w, self.seed + 71, scales=(4, 8, 16, 32, 96), gain=0.55)
        self.paper_fine = fbm(h, w, self.seed + 72, scales=(64, 128, 256), gain=0.5)

    def _curve(self, u):
        u = np.asarray(u, np.float32)
        x = (self.A * 0.92 * np.sin(TAU * 3.0 * u + 0.0)
             + self.A * 0.42 * np.sin(TAU * 5.0 * u + 1.1)
             + self.A * 0.20 * np.sin(TAU * 2.0 * u + 2.4))
        y = (self.A * 0.92 * np.sin(TAU * 2.0 * u + 0.6)
             + self.A * 0.42 * np.sin(TAU * 7.0 * u + 2.0)
             + self.A * 0.20 * np.sin(TAU * 4.0 * u + 3.3))
        return self.w * 0.5 + x, self.h * 0.52 + y * 0.92

    def render(self, t):
        h, w, L = self.h, self.w, self.loop_seconds
        u = (t % L) / L
        # ورق بإضاءة دافئة ناعمة
        paper = 0.80 + 0.10 * self.paper + 0.04 * self.paper_fine
        img = np.zeros((h, w, 3), np.float32)
        img += paper[:, :, None] * np.array([0.98, 0.955, 0.90], np.float32)
        img *= (0.80 + 0.20 * self.vig)[:, :, None]
        # المنحنى بيترسم تدريجيًا (والقلم بيكمّل من أول الشكل ⇒ حلقة مقفولة)
        prog = min(1.0, u / self.span)
        n_show = max(2, int(prog * self.xs.size))
        sel = np.arange(n_show, dtype=np.int32)
        xs = self.xs[sel]; ys = self.ys[sel]
        ink = np.zeros((h, w, 3), np.float32)                  # طبقة حبر (بتتخصم من الورق)
        for k in range(0, n_show, 260):
            sl = slice(k, min(n_show, k + 260))
            splat_fast(ink, xs[sl], ys[sl], (0.55 * self.br[sl]), (1.0, 1.0, 1.0))
        splat_fast(ink, xs, ys, np.full(xs.size, 0.55, np.float32), (1.0, 1.0, 1.0))
        ink = np.clip(ink.mean(axis=2), 0.0, 1.0)
        img *= (1.0 - ink * 0.93)[:, :, None]                   # الحبر يغمّق
        img += (ink * 0.05)[:, :, None] * np.array([0.10, 0.16, 0.42], np.float32)  # مسحة أزرق
        glow(img, float(xs[-1]), float(ys[-1]), 16.0, (0.10, 0.12, 0.22), 0.35, 2.2)
        # رأس القلم المعدني
        glow(img, float(xs[-1]) - 3, float(ys[-1]) - 4, 7.0, (0.55, 0.55, 0.58), 0.85, 3.0)
        glow(img, float(xs[-1]), float(ys[-1]), 3.0, (0.92, 0.92, 0.95), 0.55, 3.0)
        return np.clip(img, 0.0, 1.3)


# ────────────────────────────── ملصقات متحركة (Stingers) ──────────────────────────────

class Confetti(Scene):
    """انفجار قصاصات ملوّنة — للمفاجآت واللحظات المضحكة."""
    name = "stinger_confetti"
    loop_seconds = 3.0

    def prepare(self):
        rng = np.random.default_rng(self.seed + 71)
        n = 260
        self.x0 = rng.random(n, dtype=np.float32) * self.w
        self.y0 = rng.random(n, dtype=np.float32) * self.h * 0.6
        self.vx = (rng.random(n, dtype=np.float32) - 0.5) * 300.0
        self.vy = -(140.0 + rng.random(n, dtype=np.float32) * 280.0)
        self.ph = rng.random(n, dtype=np.float32) * TAU
        self.col = (rng.random((n, 3), dtype=np.float32) * 0.7 + 0.3)

    def render(self, t):
        u = (t % self.loop_seconds) / self.loop_seconds
        gt = u * 1.5
        img = np.zeros((self.h, self.w, 3), np.float32)
        x = self.x0 + self.vx * gt + 30.0 * np.sin(TAU * u + self.ph)
        y = self.y0 + self.vy * gt + 260.0 * gt * gt
        alive = (y < self.h + 30) & (y > -40)
        x, y, c = x[alive], y[alive], self.col[alive]
        idx = (np.clip(y, 0, self.h - 1).astype(np.int64) * self.w
               + np.clip(x, 0, self.w - 1).astype(np.int64))
        for ch in range(3):
            img[:, :, ch] += np.bincount(idx, weights=c[:, ch] * 1.3,
                                         minlength=self.h * self.w).reshape(self.h, self.w).astype(np.float32)
        return img


class Glitch(Scene):
    """تشويش رقمي — انتقالات قوية للشورتس."""
    name = "stinger_glitch"
    loop_seconds = 2.0

    def render(self, t):
        h, w = self.h, self.w
        u = (t % self.loop_seconds) / self.loop_seconds
        img = np.zeros((h, w, 3), np.float32)
        bars = (np.sin(TAU * (u * 3.0 + np.arange(h, dtype=np.float32) / 9.0)) > 0.6).astype(np.float32)
        img += bars[:, None, None] * 0.35 * np.array([0.4, 0.9, 1.0], np.float32)
        rng = np.random.default_rng(int(u * 24) + 3)
        for _ in range(14):
            y = int(rng.integers(0, h - 12)); hh = int(rng.integers(3, 14))
            x = int(rng.integers(-w // 3, w)); ww = int(rng.integers(w // 6, w // 2))
            col = rng.random(3, dtype=np.float32) * 0.8
            y0, y1 = y, min(h, y + hh); x0, x1 = max(0, x), min(w, x + ww)
            if y1 > y0 and x1 > x0:
                img[y0:y1, x0:x1] += col
        return img * 0.9


class ZoomPunch(Scene):
    """نبضة زووم + وميض — للتأكيد على لحظة."""
    name = "stinger_zoom"
    loop_seconds = 1.5

    def render(self, t):
        u = (t % self.loop_seconds) / self.loop_seconds
        img = np.zeros((self.h, self.w, 3), np.float32)
        rr = np.sqrt(((self.xx - self.w / 2) / (self.w * 0.5)) ** 2
                     + ((self.yy - self.h / 2) / (self.h * 0.5)) ** 2)
        ring = np.exp(-((rr - u * 1.25) ** 2) * 90.0)
        img += (ring * (1 - u))[:, :, None] * np.array([1.0, 0.95, 0.85], np.float32)
        img += max(0.0, 1.0 - u * 5.0) * 0.35
        return img


class InkWipe(Scene):
    """مسحة حبر سينمائية — انتقال بين المشاهد."""
    name = "stinger_ink"
    loop_seconds = 2.0

    def prepare(self):
        self.tex = fbm(self.h, self.w, self.seed + 81, scales=(8, 16, 32, 64), gain=0.65)

    def render(self, t):
        u = (t % self.loop_seconds) / self.loop_seconds
        edge = smoothstep((u - 0.15) / 0.5)
        m = np.clip(edge * 1.35 - self.tex * 0.55, 0.0, 1.0)
        img = np.zeros((self.h, self.w, 3), np.float32)
        img += m[:, :, None] * np.array([0.10, 0.07, 0.16], np.float32)
        img += (np.clip(m - 0.85, 0, None) * 3.0)[:, :, None] * np.array([0.5, 0.4, 0.9], np.float32)
        return img


# ────────────────────────────── السجل + الترميز ──────────────────────────────

SCENES = {
    "starfield": Starfield, "rain_glass": RainGlass, "ocean": Ocean, "aurora": Aurora,
    "fireplace": Fireplace, "sand_table": SandTable, "pendulum_wave": PendulumWave,
    "harmonograph": Harmonograph, "stinger_confetti": Confetti, "stinger_glitch": Glitch,
    "stinger_zoom": ZoomPunch, "stinger_ink": InkWipe,
}

SLEEP_SCENES = ("starfield", "rain_glass", "ocean", "aurora", "fireplace")
SMILE_SCENES = ("sand_table", "pendulum_wave", "harmonograph", "stinger_confetti",
                "stinger_glitch", "stinger_zoom", "stinger_ink")


def make_scene(name: str, w: int = 1280, h: int = 720, fps: int = 30, seed: int = 7) -> Scene:
    if name not in SCENES:                 # ممكن يكون مشهد 3D — بيتسجّل عند الاستيراد
        try:
            from . import render3d  # noqa: F401
        except Exception:
            pass
    if name not in SCENES:
        raise KeyError(f"مشهد غير معروف: {name}")
    return SCENES[name](w=w, h=h, fps=fps, seed=seed)


def black_screen(w: int = 1280, h: int = 720, fps: int = 30, seed: int = 7) -> Scene:
    """الشاشة السوداء «الحقيقية» (اللي بتجيب مئات الملايين) + تنفّس خفيف جدًا يمنع الجمود."""
    class _Black(Scene):
        name = "black_screen"
        grain_amp = 0.004

        def render(self, t):
            u = (t % self.loop_seconds) / self.loop_seconds
            v = 0.007 + 0.004 * math.sin(TAU * u)
            return np.full((self.h, self.w, 3), v, np.float32)
    return _Black(w=w, h=h, fps=fps, seed=seed)


def encode(scene: Scene, seconds: float, path, fps: int | None = None,
           out_w: int | None = 1920, out_h: int | None = 1080, crf: int = 20,
           preset: str = "veryfast", verbose: bool = False,
           cinema: str | None = None, maxrate: str | None = None) -> pathlib.Path:
    """
    ترميز حلقة فيديو (H.264 · yuv420p · faststart) بلا تجميع كادرات في الرام.
    cinema: اسم مظهر الجودة السينمائية ("cinema_cool" … ) — لو None بناخد مظهر المشهد الافتراضي.
    """
    cinema = cinema if cinema is not None else LOOKS.get(scene.name, "cinema_night")
    fps = int(fps or scene.fps)
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(round(seconds * fps))
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{scene.w}x{scene.h}", "-r", str(fps),
           "-i", "-"]
    if out_w and out_h and (out_w, out_h) != (scene.w, scene.h):
        cmd += ["-vf", f"scale={out_w}:{out_h}:flags=lanczos"]
    if maxrate:
        cmd += ["-maxrate", maxrate, "-bufsize", maxrate]
    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-g", str(fps * 2), "-keyint_min", str(fps), "-sc_threshold", "0",
            "-movflags", "+faststart", str(path)]
    if scene.stateful:
        scene.reset()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    try:
        for i in range(frames):
            fr = scene.frame(i / fps, index=i)
            if cinema and cinema != "clean":
                depth = scene.depth(i / fps) if hasattr(scene, "depth") else None
                out = _grade.apply(fr, preset=cinema, depth=depth,
                                   sun_xy=getattr(scene, "sun_xy", (0.7, 0.25)), seed=i)
                fr = (np.clip(out, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
            proc.stdin.write(memoryview(fr))
    finally:
        if proc.stdin:
            proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "ignore") if proc.stderr else ""
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg فشل ({rc}): {err[:400]}")
    if verbose:
        print(f"✅ {path.name} · {frames} كادر · {seconds:.1f} ث")
    return path


def long_video(loop_path, out, total_seconds: float, audio_wav=None, audio_loop: bool = True,
               verbose: bool = False):
    """فيديو طويل من حلقة قصيرة **بلا إعادة ترميز** ⇒ 10 ساعات في ثواني، وبلا فجوات."""
    loop_path, out = pathlib.Path(loop_path), pathlib.Path(out)
    probe = subprocess.run([FFMPEG, "-hide_banner", "-i", str(loop_path)], capture_output=True)
    dur = 60.0
    for line in probe.stderr.decode("utf-8", "ignore").splitlines():
        if "Duration:" in line:
            hh, mm, ss = line.split("Duration:")[1].split(",")[0].strip().split(":")
            dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
    loops = max(1, int(math.ceil(total_seconds / max(dur, 0.1))))
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-stream_loop", str(loops), "-i", str(loop_path)]
    if audio_wav:
        cmd += (["-stream_loop", str(loops)] if audio_loop else []) + ["-i", str(audio_wav)]
    cmd += ["-t", f"{total_seconds:.3f}", "-c:v", "copy"]
    if audio_wav:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]
    cmd += ["-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    if verbose:
        print(f"✅ {out.name} · {total_seconds/3600:.1f} ساعة · {loops} تكرار")
    return out


def render_showcase(out_dir, seconds: float = 8.0, w: int = 1280, h: int = 720,
                    fps: int = 30, scenes=None, cinema: str | None = None) -> list:
    """عيّنات قصيرة من كل مشهد — للمراجعة بالعين."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for name in (scenes or list(SCENES)):
        sc = make_scene(name, w=w, h=h, fps=fps)
        made.append(encode(sc, seconds, out_dir / f"{name}.mp4",
                           out_w=w * 2, out_h=h * 2, crf=23, cinema=cinema))
    return made


if __name__ == "__main__":
    import sys
    which = sys.argv[1:] or ["starfield"]
    for nm in which:
        sc = make_scene(nm)
        p = encode(sc, min(sc.loop_seconds, 10.0), f"out/{nm}.mp4", verbose=True)
        print("→", p)
