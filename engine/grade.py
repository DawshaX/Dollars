"""
🎞️ طقم الجودة السينمائية (Post-Processing) — Dollars Studio
============================================================
ده الفرق بين «شكل هواة» و«شكل إنتاج»: نفس المشهد، لكن بعد مرحلة تصنيع كاملة:

  1. تصحيح ألوان (Color Grade) بأسلوب أفلام: Teal & Orange · Nocturne · Warm Cinema
  2. Tonemap فيلمي (ACES-like) ⇒ إضاءة متماسكة بلا حرق أبيض.
  3. Bloom (توهّج الأضواء) + Halation (هالة حمراء حوالين الإضاءة القوية).
  4. عمق الميدان (Depth of Field) حقيقي من خريطة العمق — الخلفية والتقدمة بوكيه.
  5. فرق لوني سطري (Chromatic Aberration) خفيف جدًا — طابع عدسات.
  6. توهّج إشعاعي (God rays) من الشمس/القمر خلال السحب.
  7. غبار فيلمي + فينييت + عدسة عريضة (letterbox اختياري).

كله متجهّز بـ numpy (سريع · بلا GPU · بلا مكتبات خارجية · بلا أي حقوق).

الواجهة:
    from engine import grade
    out = grade.apply(img, preset="cinema_night", depth=depth, sun=(x, y, strength))
    # أو على مستوى المشهد:
    visuals.encode(scene, seconds, "out.mp4", cinema="cinema_night")
"""
from __future__ import annotations

import math

import numpy as np

# ─────────────────────────── عمليات أساسية ───────────────────────────

def _blur(img: np.ndarray, radius: float) -> np.ndarray:
    """بلر صندوقي سريع (cumsum) على المحورين — بديل رخيص وسريع للغاوسي."""
    r = max(1, int(round(radius)))
    if r < 1:
        return img
    out = img
    for axis in (0, 1):
        n = out.shape[axis]
        k = min(r, max(1, n // 2))
        pad = [(0, 0)] * out.ndim
        pad[axis] = (k, k)
        x = np.pad(out, pad, mode="edge")
        c = np.cumsum(x, axis=axis, dtype=np.float32)
        zero_shape = list(c.shape); zero_shape[axis] = 1
        c = np.concatenate([np.zeros(zero_shape, np.float32), c], axis=axis)
        n_ = c.shape[axis]
        sl_hi = [slice(None)] * out.ndim; sl_lo = [slice(None)] * out.ndim
        sl_hi[axis] = slice(2 * k + 1, n_)
        sl_lo[axis] = slice(0, n_ - (2 * k + 1))
        out = ((c[tuple(sl_hi)] - c[tuple(sl_lo)]) / (2 * k + 1)).astype(np.float32)
    return out


def _down(img: np.ndarray, f: int = 4) -> np.ndarray:
    h, w = img.shape[:2]
    h2, w2 = max(1, h // f), max(1, w // f)
    return img[:h2 * f, :w2 * f].reshape(h2, f, w2, f, -1).mean(axis=(1, 3))


def _up(img: np.ndarray, size) -> np.ndarray:
    h, w = size
    ys = np.linspace(0, img.shape[0] - 1, h).astype(np.int32)
    xs = np.linspace(0, img.shape[1] - 1, w).astype(np.int32)
    return img[ys][:, xs]


# ─────────────────────────── المكوّنات ───────────────────────────

def bloom(img: np.ndarray, threshold: float = 0.72, strength: float = 0.55,
          radius: int = 26) -> np.ndarray:
    """توهّج الأضواء: نأخذ الأنوار الساطعة بس، نبلّرها، ونضيفها."""
    lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mask = np.clip((lum - threshold) / max(1e-3, 1.0 - threshold), 0.0, 1.0)[:, :, None]
    bright = img * mask
    small = _down(bright, 4)
    small = _blur(small, max(2, radius // 4))
    small = _blur(small, max(2, radius // 4))
    return img + strength * _up(small, img.shape[:2])


def halation(img: np.ndarray, threshold: float = 0.80, strength: float = 0.30,
             radius: int = 34) -> np.ndarray:
    """هالة حمراء-برتقالية حوالين الأنوار (زي أفلام 35mm)."""
    lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    mask = np.clip((lum - threshold) * 4.0, 0.0, 1.0)[:, :, None]
    red = img * mask * np.array([1.0, 0.42, 0.20], np.float32)
    small = _down(red, 4)
    small = _blur(small, max(2, radius // 4))
    return img + strength * _up(small, img.shape[:2])


def dof(img: np.ndarray, depth: np.ndarray | None, focus: float = 0.45,
        aperture: float = 0.06, max_blur: float = 9.0) -> np.ndarray:
    """
    عمق الميدان: بنبلّر بثلاث درجات مختلفة ونختار لكل بكسل حسب بعده عن مستوى التركيز.
    depth: 0 = قريب جدًا · 1 = بعيد · None = تقدير بسيط من التدرّج الرأسي.
    """
    h, w = img.shape[:2]
    if depth is None:
        return img
    if depth.shape != (h, w):
        depth = _up(depth[:, :, None], (h, w))[:, :, 0]
    coc = np.clip(np.abs(depth - focus) / max(aperture, 1e-3), 0.0, 1.0) ** 0.85
    b1 = _blur(img, max_blur * 0.35)
    b2 = _blur(img, max_blur * 0.75)
    b3 = _blur(img, max_blur * 1.4)
    out = img.copy()
    m1 = (coc > 0.20) & (coc <= 0.55)
    m2 = (coc > 0.55) & (coc <= 0.85)
    m3 = coc > 0.85
    k1 = np.clip((coc - 0.20) / 0.35, 0, 1)[:, :, None]
    k2 = np.clip((coc - 0.55) / 0.30, 0, 1)[:, :, None]
    k3 = np.clip((coc - 0.85) / 0.15, 0, 1)[:, :, None]
    out = np.where(m1[:, :, None], img * (1 - k1) + b1 * k1, out)
    out = np.where(m2[:, :, None], b1 * (1 - k2) + b2 * k2, out)
    out = np.where(m3[:, :, None], b2 * (1 - k3) + b3 * k3, out)
    return out


def god_rays(img: np.ndarray, sun_xy=(0.7, 0.25), strength: float = 0.28,
             threshold: float = 0.78, steps: int = 5) -> np.ndarray:
    """أشعة من الشمس/القمر: نبلّر الأنوار في اتجاه الشمس ونضيفه (رخيص ومؤثّر)."""
    h, w = img.shape[:2]
    lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    src = np.clip((lum - threshold) * 3.0, 0.0, 1.0)[:, :, None] * img
    sx, sy = int(sun_xy[0] * w), int(sun_xy[1] * h)
    acc = np.zeros_like(img)
    scale = 1.0
    for i in range(steps):
        scale *= 0.62
        sh = int((sx - w / 2) * (i + 1) * 0.05)
        sv = int((sy - h / 2) * (i + 1) * 0.05)
        shifted = np.roll(np.roll(src, sh, axis=1), sv, axis=0)
        acc += _blur(shifted, 8 + 6 * i) * scale
    return img + strength * acc / steps


def chromatic_aberration(img: np.ndarray, amount: float = 1.1) -> np.ndarray:
    """فرق لوني خفيف عند الأطراف (طابع عدسة) — بـ roll واحد لكل قناة."""
    h, w = img.shape[:2]
    out = img.copy()
    v = (np.arange(h, dtype=np.float32) / h - 0.5)[:, None]
    u = (np.arange(w, dtype=np.float32) / w - 0.5)[None, :]
    r2 = (v * v + u * u)
    dr = (amount * r2 * 2.0)
    dy = np.round(dr * 1.0).astype(np.int32); dx = np.round(dr * 1.0).astype(np.int32)
    # نُزحف القنوات الحمراء والزرقاء للخارج
    for c, sgn in ((0, 1), (2, -1)):
        out[:, :, c] = _shift_2d(img[:, :, c], sgn * dx, sgn * dy)
    return out


def _shift_2d(chan: np.ndarray, dx_map, dy_map) -> np.ndarray:
    h, w = chan.shape
    rows = np.clip(np.arange(h)[:, None] + dy_map, 0, h - 1)
    cols = np.clip(np.arange(w)[None, :] + dx_map, 0, w - 1)
    return chan[rows, cols]


def film_tonemap(img: np.ndarray, exposure: float = 1.0) -> np.ndarray:
    """Tonemap فيلمي (تقريب ACES) ⇒ منظر سينمائي بلا حرق."""
    x = np.clip(img * exposure, 0.0, 8.0)
    return np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0)


GRADES = {
    # (ضرب القنوات, إزاحة القنوات, جاما, التشبّع, الصبغة, شدّة الـS-curve)
    "none":         (((1.00, 1.00, 1.00), (0, 0, 0), (1, 1, 1), 1.00, (0, 0, 0), 0.00)),
    "cinema_night": (((1.02, 1.03, 1.14), (0.004, 0.006, 0.012), (1.00, 1.00, 0.98), 1.10, (0.00, 0.00, 0.02), 0.34)),
    "cinema_warm":  (((1.10, 1.02, 0.92), (0.006, 0.003, 0.000), (0.98, 1.00, 1.04), 1.06, (0.02, 0.01, -0.01), 0.32)),
    "teal_orange":  (((1.06, 0.99, 0.95), (0.000, 0.002, 0.008), (1.00, 0.99, 1.02), 1.16, (0.01, 0.00, 0.02), 0.38)),
    "nocturne":     (((0.96, 1.00, 1.16), (0.002, 0.004, 0.014), (1.02, 1.00, 0.96), 1.14, (0.00, 0.00, 0.03), 0.34)),
    "dream":        (((1.04, 1.00, 1.08), (0.010, 0.008, 0.014), (0.96, 0.98, 1.00), 1.12, (0.02, 0.00, 0.03), 0.26)),
    "golden":       (((1.14, 1.04, 0.86), (0.008, 0.004, 0.000), (0.97, 1.00, 1.06), 1.08, (0.03, 0.015, -0.01), 0.34)),
}


def color_grade(img: np.ndarray, preset: str = "cinema_night") -> np.ndarray:
    mul, lift, gam, sat, tint, s_curve = GRADES.get(preset, GRADES["none"])
    x = np.clip(img * np.asarray(mul, np.float32) + np.asarray(lift, np.float32), 0.0, 1.0)
    x = np.power(x, 1.0 / np.asarray(gam, np.float32))
    lum = (x @ np.array([0.2126, 0.7152, 0.0722], np.float32))[:, :, None]
    x = lum + (x - lum) * sat + np.asarray(tint, np.float32)
    x = np.clip(x, 0.0, 1.0)
    if s_curve > 0:      # منحنى S معتدل: يرجّع «الطعمة» بعد الـtonemap (بلا حرق أو سحق)
        x = np.clip(x + s_curve * x * (1.0 - x) * (2.0 * x - 1.0), 0.0, 1.0)
    return x


def grain(img: np.ndarray, amount: float = 0.012, seed: int = 0) -> np.ndarray:
    h, w = img.shape[:2]
    rng = np.random.default_rng(seed)
    g = rng.normal(0.0, 1.0, (h, w, 1)).astype(np.float32) * amount
    return np.clip(img + g, 0.0, 1.0)


def vignette(img: np.ndarray, amount: float = 0.30, softness: float = 1.6) -> np.ndarray:
    h, w = img.shape[:2]
    y = (np.arange(h, dtype=np.float32) / max(1, h - 1) - 0.5) * 2
    x = (np.arange(w, dtype=np.float32) / max(1, w - 1) - 0.5) * 2
    r2 = (y[:, None] ** 2 + x[None, :] ** 2)
    v = np.clip(1.0 - amount * (r2 ** (softness * 0.6)), 0.0, 1.0).astype(np.float32)
    return img * v[:, :, None]


def letterbox(img: np.ndarray, ratio: float = 2.39) -> np.ndarray:
    """شريط سينمائي (اختياري — الشاشة الكاملة أحسن للنوم، بس الأفضل للقِصص)."""
    h, w = img.shape[:2]
    target = int(round(w / ratio))
    if target >= h:
        return img
    bar = (h - target) // 2
    out = img.copy()
    out[:bar] *= 0.02
    out[h - bar:] *= 0.02
    return out


def unsharp(img: np.ndarray, amount: float = 0.22, radius: int = 2) -> np.ndarray:
    return np.clip(img + amount * (img - _blur(img, radius)), 0.0, 1.0)


PRESETS = {
    # الاسم: (إعدادات كاملة) — السيناريوهات اللي بنستخدمها فعليًا
    "cinema_night": dict(grade="cinema_night", exposure=1.10, bloom=0.42, halation=0.26,
                         dof=True, ca=0.9, rays=0.0, grain=0.009, vig=0.30, sharp=0.20),
    "cinema_warm": dict(grade="golden", exposure=1.10, bloom=0.36, halation=0.30,
                        dof=True, ca=0.8, rays=0.22, grain=0.011, vig=0.30, sharp=0.20),
    "cinema_cool": dict(grade="nocturne", exposure=1.08, bloom=0.46, halation=0.20,
                        dof=True, ca=1.0, rays=0.10, grain=0.009, vig=0.32, sharp=0.20),
    "story": dict(grade="teal_orange", exposure=1.05, bloom=0.45, halation=0.28,
                  dof=True, ca=0.8, rays=0.18, grain=0.014, vig=0.32, sharp=0.18),
    "satisfying": dict(grade="dream", exposure=1.03, bloom=0.38, halation=0.20,
                       dof=True, ca=1.4, rays=0.0, grain=0.008, vig=0.22, sharp=0.22),
    "clean": dict(grade="none", exposure=1.0, bloom=0.0, halation=0.0, dof=False, ca=0.0,
                  rays=0.0, grain=0.0, vig=0.0, sharp=0.0),
}


def apply(img: np.ndarray, preset: str = "cinema_night", depth: np.ndarray | None = None,
          sun_xy=(0.7, 0.25), seed: int = 0, focus: float = 0.72, aperture: float = 0.30,
          max_blur: float = 3.0) -> np.ndarray:
    """
    img: float32 0..1 (H,W,3) · depth: 0 قريب → 1 بعيد (أو None) · يقبل uint8 ويحوّله.
    """
    if img.dtype == np.uint8:
        img = img.astype(np.float32) / 255.0
    if preset in (None, "clean"):
        return np.clip(img, 0.0, 1.0)
    p = PRESETS.get(preset, PRESETS["clean"])
    x = img
    if p["rays"] > 0:
        x = god_rays(x, sun_xy=sun_xy, strength=p["rays"], threshold=0.72)
    if p["bloom"] > 0:
        x = bloom(x, threshold=0.70, strength=p["bloom"], radius=30)
    if p["halation"] > 0:
        x = halation(x, threshold=0.78, strength=p["halation"], radius=40)
    if p["dof"] and depth is not None:
        x = dof(x, depth, focus=focus, aperture=aperture, max_blur=max_blur)
    x = film_tonemap(x, exposure=p["exposure"])
    x = color_grade(x, p["grade"])
    if p["ca"] > 0:
        x = chromatic_aberration(x, amount=p["ca"])
    if p["sharp"] > 0:
        x = unsharp(x, amount=p["sharp"])
    if p["vig"] > 0:
        x = vignette(x, amount=p["vig"])
    if p["grain"] > 0:
        x = grain(x, amount=p["grain"], seed=seed)
    return np.clip(x, 0.0, 1.0)



# ─────────────── تدرّج لوني من لوحة مرجع بصري (تحليل حقيقي) ───────────────

def _hex_to_rgb(h) -> list:
    h = str(h).strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    except Exception:
        return [0.5, 0.5, 0.5]


def split_tone(img: np.ndarray, palette, strength: float = 0.45,
               protect: float = 0.55) -> np.ndarray:
    """
    تدرّج «سبليت تون» من لوحة مرجع حقيقي: بنفصل صِبغة كل لون (hue) عن سطوعه،
    ونضرب بها الظلال/النص/الأضواء كل واحد على حدة — مع الحفاظ على الألوان الأصلية بنسبة `protect`.
    النتيجة: الفيديو بياخد **مزاج وألوان المرجع** من غير ما يفقد هويته.
    """
    if not palette:
        return img
    cols = [_hex_to_rgb(c) if isinstance(c, str) else list(c) for c in palette]
    if not cols:
        return img

    def lum(c):
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def hue_only(c):
        """نفس الصِبغة بسطوع محايد ⇒ نضرب بيها بلا ما نغيّر الإضاءة."""
        l = max(lum(c), 0.06)
        return np.clip(np.array(c, np.float32) / l, 0.0, 3.0)

    srt = sorted(cols, key=lum)
    cs, cm, ch = hue_only(srt[0]), hue_only(srt[len(srt) // 2]), hue_only(srt[-1])
    x = img.astype(np.float32)
    lum_map = x @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    w_s = np.clip((0.40 - lum_map) / 0.40, 0.0, 1.0)               # الظلال
    w_h = np.clip((lum_map - 0.62) / 0.38, 0.0, 1.0)               # الأضواء
    w_m = np.clip(1.0 - w_s - w_h, 0.0, 1.0)                       # النص
    factor = 1.0 + strength * (w_s[:, :, None] * (cs - 1.0)
                               + w_m[:, :, None] * (cm - 1.0)
                               + w_h[:, :, None] * (ch - 1.0))
    out = x * np.clip(factor, 0.25, 2.2)
    out = out + (0.035 * strength) * (w_s[:, :, None] * cs)        # رفعة بسيطة للظلال (طابع فيلم)
    return np.clip(x * protect + out * (1.0 - protect), 0.0, 1.0)


def quality_report(img: np.ndarray) -> dict:
    """قياس موضوعي للجودة: تباين · تشبّع · حِدّة · نطاق ديناميكي (للمراجعة قبل النشر)."""
    x = img.astype(np.float32) / 255.0 if img.dtype == np.uint8 else img.astype(np.float32)
    lum = x @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    sat = float(np.mean(x.max(axis=2) - x.min(axis=2)))
    lap = np.abs(4 * lum[1:-1, 1:-1] - lum[:-2, 1:-1] - lum[2:, 1:-1] - lum[1:-1, :-2] - lum[1:-1, 2:])
    return {
        "mean_lum": round(float(lum.mean()), 4),
        "contrast": round(float(lum.std()), 4),
        "saturation": round(float(sat), 4),
        "sharpness": round(float(lap.mean()), 5),
        "black_clip": round(float((lum < 0.005).mean()), 4),
        "white_clip": round(float((lum > 0.995).mean()), 4),
    }
