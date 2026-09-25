"""
🧰 أدوات التوليد الإجرائي المشتركة — Dollars Studio
====================================================
ضجيج كسري (fBm) · ضجيج دوري (حتى يبقى المشهد حلقة مثالية) · رشّ نقاط مضيئة ·
هالات · تنعيم. كلها numpy خالص: سريعة، بلا مكتبات، وبلا أي حقوق.

كل المشاهد (2D و 3D) بتستخدم الملف ده — عشان الجودة والسلوك يبقوا موحّدين.
"""
from __future__ import annotations

import math

import numpy as np

try:  # ffmpeg من imageio (مفيش ffmpeg نظام على البيئة دي)
    from imageio_ffmpeg import get_ffmpeg_exe

    FFMPEG = get_ffmpeg_exe()
except Exception:  # pragma: no cover
    FFMPEG = "ffmpeg"

TAU = 2.0 * math.pi


# ────────────────────────────── أدوات رياضية ──────────────────────────────

def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _bilerp(a: np.ndarray, h: int, w: int) -> np.ndarray:
    gh, gw = a.shape
    ys = np.linspace(0.0, gh - 1, h, dtype=np.float32)
    xs = np.linspace(0.0, gw - 1, w, dtype=np.float32)
    y0 = np.floor(ys).astype(np.int32); y1 = np.minimum(y0 + 1, gh - 1); fy = (ys - y0)[:, None]
    x0 = np.floor(xs).astype(np.int32); x1 = np.minimum(x0 + 1, gw - 1); fx = (xs - x0)[None, :]
    fy = smoothstep(fy); fx = smoothstep(fx)
    top = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    return (top * (1 - fy) + bot * fy).astype(np.float32)


def fbm(h: int, w: int, seed: int = 0, scales=(4, 8, 16, 32, 64, 128),
        gain: float = 0.5) -> np.ndarray:
    """ضجيج كسري (fBm) سريع — بيراميد من شبكات عشوائية."""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for s in scales:
        gh, gw = max(2, h // s + 2), max(2, w // s + 2)
        rng = np.random.default_rng(seed * 100003 + s)
        out += amp * _bilerp(rng.random((gh, gw), dtype=np.float32), h, w)
        tot += amp
        amp *= gain
    out /= max(tot, 1e-6)
    out -= float(out.min())
    out /= max(float(np.ptp(out)), 1e-6)
    return out


def pick_period(size: int, target: int) -> int:
    """أقرب قاسم للمقاس المطلوب — يضمن تقطيعًا صحيحًا 100% بلا كسر عند الحدود."""
    size, target = int(size), max(8, int(target))
    for d in range(min(target, size // 2), 7, -1):
        if size % d == 0:
            return d
    for d in range(target, size // 2 + 1):
        if size % d == 0:
            return d
    return size


def tiled_fbm(h: int, w: int, seed: int, period: int, axis: int = 1, **kw) -> np.ndarray:
    """
    ضجيج بمقاس `period` بيتكرّر لحد المقاس الكامل (axis=1 أفقي · axis=0 رأسي).
    ⇒ أي إزاحة من مضاعفات `period` بترجّع المشهد لأصله = **حلقة مثالية** للحركة البطيئة.
    """
    period = max(8, int(period))
    if axis == 0:
        base = fbm(min(period, h), w, seed, **kw)
        if period >= h:
            return base
        reps = int(math.ceil(h / period)) + 1
        return np.ascontiguousarray(np.tile(base, (reps, 1))[:h, :])
    base = fbm(h, min(period, w), seed, **kw)
    if period >= w:
        return base
    reps = int(math.ceil(w / period)) + 1
    return np.ascontiguousarray(np.tile(base, (1, reps))[:, :w])


def tiled_fbm2(h: int, w: int, seed: int, ph: int, pw: int, **kw) -> np.ndarray:
    """ضجيج دوري **رأسيًا وأفقيًا** — لأي نسيج بيتحرك في الاتجاهين (لهب · دخان · ماء)."""
    ph, pw = pick_period(h, ph), pick_period(w, pw)
    base = fbm(ph, pw, seed, **kw)
    ry = int(math.ceil(h / ph)) + 1
    rx = int(math.ceil(w / pw)) + 1
    return np.ascontiguousarray(np.tile(base, (ry, rx))[:h, :w])


def roll_px(arr: np.ndarray, px: float, axis: int = 1) -> np.ndarray:
    """إزاحة بمضاعفات دورية (تستخدم مع tiled_fbm)."""
    return np.roll(arr, int(round(px)), axis=axis)


def splat(img: np.ndarray, xs, ys, bright, color, wrap: bool = True) -> None:
    """إضافة نقاط مضيئة بأعلى دقة (bincount) — للعناصر المهمة القليلة."""
    h, w = img.shape[:2]
    xs = np.asarray(xs, np.float32).ravel(); ys = np.asarray(ys, np.float32).ravel()
    bright = np.asarray(bright, np.float32).ravel()
    x0 = np.floor(xs).astype(np.int32); y0 = np.floor(ys).astype(np.int32)
    fx = xs - x0; fy = ys - y0
    flat3 = img.reshape(-1, 3)
    for dx in (0, 1):
        for dy in (0, 1):
            wt = bright * (fx if dx else 1.0 - fx) * (fy if dy else 1.0 - fy)
            xi, yi = x0 + dx, y0 + dy
            if wrap:
                xi = np.mod(xi, w); yi = np.mod(yi, h)
                m = np.ones_like(wt, bool)
            else:
                m = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
            if not np.any(m):
                continue
            idx = yi[m].astype(np.int64) * w + xi[m].astype(np.int64)
            wt = wt[m]
            for c in range(3):
                acc = np.bincount(idx, weights=wt, minlength=h * w).astype(np.float32)
                flat3[:, c] += acc * np.float32(color[c])


def splat_fast(img: np.ndarray, xs, ys, bright, color, wrap: bool = True) -> None:
    """نفس الفكرة لكن بنصف الدقة ثم تُرفع ⇒ 4× أسرع (للنجوم · المطر · الجمر · الكور)."""
    h, w = img.shape[:2]
    h2, w2 = max(1, h // 2), max(1, w // 2)
    xs = np.asarray(xs, np.float32).ravel() * 0.5
    ys = np.asarray(ys, np.float32).ravel() * 0.5
    bright = np.asarray(bright, np.float32).ravel()
    x0 = np.floor(xs).astype(np.int32); y0 = np.floor(ys).astype(np.int32)
    fx = xs - x0; fy = ys - y0
    acc = np.zeros((3, h2 * w2), np.float32)
    for dx in (0, 1):
        for dy in (0, 1):
            wt = bright * (fx if dx else 1.0 - fx) * (fy if dy else 1.0 - fy)
            xi, yi = x0 + dx, y0 + dy
            if wrap:
                xi = np.mod(xi, w2); yi = np.mod(yi, h2)
                m = np.ones_like(wt, bool)
            else:
                m = (xi >= 0) & (xi < w2) & (yi >= 0) & (yi < h2)
            if not np.any(m):
                continue
            idx = yi[m].astype(np.int64) * w2 + xi[m].astype(np.int64)
            wt = wt[m]
            for c in range(3):
                acc[c] += np.bincount(idx, weights=wt, minlength=h2 * w2).astype(np.float32)
    small = acc.reshape(3, h2, w2).transpose(1, 2, 0)
    up = np.repeat(np.repeat(small, 2, axis=0), 2, axis=1)
    if up.shape[0] != h or up.shape[1] != w:      # الأبعاد الفردية: نكمّل بتمدید الحافة
        up = np.pad(up, ((0, max(0, h - up.shape[0])), (0, max(0, w - up.shape[1])), (0, 0)),
                    mode="edge")[:h, :w]
    img += up * np.asarray(color, np.float32)[None, None, :]


def upscale(img: np.ndarray, size) -> np.ndarray:
    """تكبير صورة float 0..1 لمقاس معيّن (بيستخدم PIL لو متاح — أسرع وأنعم)."""
    h, w = size
    if img.shape[0] == h and img.shape[1] == w:
        return img
    try:
        from PIL import Image
        im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
        return np.asarray(im.resize((w, h), Image.BILINEAR), np.float32) / 255.0
    except Exception:
        ys = np.linspace(0, img.shape[0] - 1, h).astype(np.int32)
        xs = np.linspace(0, img.shape[1] - 1, w).astype(np.int32)
        return img[ys][:, xs]


def glow(img: np.ndarray, cx: float, cy: float, radius: float, color, power: float = 1.0,
         softness: float = 2.2) -> None:
    """هالة ناعمة (قمر · لمبة · لمعة كورة)."""
    h, w = img.shape[:2]
    r = max(2.0, float(radius))
    x0, x1 = max(0, int(cx - r)), min(w, int(cx + r) + 1)
    y0, y1 = max(0, int(cy - r)), min(h, int(cy + r) + 1)
    if x0 >= x1 or y0 >= y1:
        return
    xs = np.arange(x0, x1, dtype=np.float32)[None, :] - np.float32(cx)
    ys = np.arange(y0, y1, dtype=np.float32)[:, None] - np.float32(cy)
    d = np.sqrt(ys * ys + xs * xs) / r
    fall = np.exp(-np.power(d, softness) * 2.2) + 0.35 * np.exp(-np.power(d, softness * 2.6) * 6.0)
    for c in range(3):
        img[y0:y1, x0:x1, c] += fall * np.float32(color[c] * power)


def _mix(a, b, u):
    return a * (1.0 - u) + b * u


# ────────────────────────────── قياس ──────────────────────────────

def duration(path) -> float | None:
    """مدة ملف فيديو/صوت بالثواني (بنقراها من ffmpeg نفسه — بلا ffprobe)."""
    import re
    import subprocess
    try:
        r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True)
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr.decode("utf-8", "ignore"))
        if not m:
            return None
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:
        return None
