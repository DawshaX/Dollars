"""
✨ طبقة الإضافات البصرية (FX) — Dollars Studio
==============================================
إضافات **مولّدة بالكود** بتتحطّ على الكادر في المونتاج: شرائط ضوء · هالة · لمعة · غبار ·
بوكيه · بلوم · خطوط مسح · حبيبات فيلم · حجاب ناعم — كلها تتحسب لحظة الرندر (مخزونها لا نهائي
وبلا أي حقوق: مفيش ملف واحد هنا، كلها معادلات).

    from engine import fx
    plan = fx.plan(rng, "satisfying", n_shots=4)      # خطة إضافات لكل مقطع
    fr = fx.apply(frame, eff, t=1.2, dur=4.0, seed=9) # تنفيذ على كادر
"""
from __future__ import annotations

import math

import numpy as np

# أنواع الإضافات (كلها متاحة في كل فيديو — المصنع بيوزّعها)
KINDS = ("light_leak", "flare", "dust", "bokeh", "bloom", "scanlines", "grain_soft", "vignette_soft",
         "sparkle_dust", "sweep")

# وزن كل نوع لكل نوع فيديو (أهم = بيتوزّع أكتر)
WEIGHTS = {
    "satisfying": {"light_leak": 2.0, "flare": 2.0, "dust": 1.4, "bokeh": 1.6, "bloom": 1.6,
                   "sparkle_dust": 2.0, "sweep": 1.6, "grain_soft": 1.0, "vignette_soft": 1.0},
    "ambience": {"light_leak": 1.0, "flare": 0.8, "dust": 1.0, "bokeh": 0.8, "bloom": 1.2,
                 "grain_soft": 2.0, "vignette_soft": 2.2, "sweep": 0.6, "sparkle_dust": 0.6},
    "story": {"light_leak": 1.2, "flare": 1.2, "dust": 1.6, "bokeh": 1.4, "bloom": 1.6,
              "sparkle_dust": 1.6, "grain_soft": 1.2, "vignette_soft": 1.2, "sweep": 1.0},
    "sleep": {"grain_soft": 1.6, "vignette_soft": 2.0, "bloom": 0.8, "dust": 0.6},
}


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(int(seed) & 0x7FFFFFFF)


def plan(rng, pillar: str = "satisfying", n_shots: int = 4) -> list:
    """خطة إضافات: كل مقطع ياخد 1-2 إضافة (والنوع حسب الفيديو)."""
    w = WEIGHTS.get(pillar, WEIGHTS["satisfying"])
    kinds = list(w)
    ws = np.array([w[k] for k in kinds], dtype=float)
    ws = ws / ws.sum()
    out = []
    for i in range(n_shots):
        n = 2 if rng.random() < 0.45 else 1
        picked, used = [], set()
        for _ in range(n):
            for _try in range(4):
                k = str(kinds[int(np.argmax(rng.random() < np.cumsum(ws)))])
                if k not in used:
                    used.add(k)
                    picked.append(dict(kind=k, at=0.0,
                                       dur=round(rng.uniform(1.2, 3.4), 2),
                                       strength=round(rng.uniform(0.35, 0.95), 2),
                                       pos=(round(rng.uniform(0.15, 0.85), 3), round(rng.uniform(0.12, 0.7), 3)),
                                       seed=int(rng.random() * 10 ** 6)))
                    break
        out.append(picked)
        del i
    return out


def _u8(frame) -> np.ndarray:
    return frame if frame.dtype == np.uint8 else (np.clip(frame, 0, 1) * 255).astype(np.uint8)


def _fade(t: float, dur: float, ease: float = 0.25) -> float:
    """ظهور واختفاء ناعم جوه مدة الإضافة."""
    if dur <= 0:
        return 1.0
    k = min(1.0, max(0.0, t / dur))
    e = max(1e-3, ease)
    return float(min(1.0, min(k / e, (1.0 - k) / e, 1.0)))


def light_leak(fr: np.ndarray, k: float = 0.6, side: str = "right") -> np.ndarray:
    """تسرّب ضوء دافئ من ركن الكادر (شكل فيلم حقيقي) — من غير شرايط حادّة."""
    h, w = fr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    ux = xs / max(1, w - 1)
    uy = ys / max(1, h - 1)
    cx, cy = (1.02 if side == "right" else -0.02), -0.06
    r = np.sqrt(((ux - cx) * 1.15) ** 2 + (uy - cy) ** 2)
    glow = np.exp(-(r ** 2) * 3.1) * 0.75 + np.exp(-(r ** 2) * 9.0) * 0.55
    edge = np.exp(-(np.clip(r - 0.55, 0, None) ** 2) * 12.0)
    amt = (glow + 0.25 * edge) * (k * 62.0)
    warm = np.stack([amt * 1.00, amt * 0.74, amt * 0.44], axis=-1)
    out = fr.astype(np.float32) + warm
    return np.clip(out, 0, 255).astype(np.uint8)


def flare(fr: np.ndarray, pos=(0.7, 0.3), k: float = 0.7) -> np.ndarray:
    h, w = fr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = pos[0] * w, pos[1] * h
    r = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / (0.30 * w)
    core = np.exp(-(r ** 2) * 14.0)
    halo = np.exp(-(r ** 2) * 2.2) * 0.5
    streak = np.exp(-(((xs - cx) / (0.55 * w)) ** 2 + ((ys - cy) / (0.012 * h)) ** 2) * 6.0) * 0.55
    add = (core * 1.0 + halo * 0.5 + streak) * (k * 170.0)
    tint = np.stack([add * 1.0, add * 0.86, add * 0.62], axis=-1)
    return np.clip(fr.astype(np.float32) + tint, 0, 255).astype(np.uint8)


def dust(fr: np.ndarray, t: float, k: float = 0.6, seed: int = 1) -> np.ndarray:
    """غبار طائر جوه الضوء — جزيئات صغيرة بتتحرك."""
    h, w = fr.shape[:2]
    rng = _rng(seed)
    n = int(38 * k + 12)
    out = fr.astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for i in range(n):
        px = ((rng.random() + t * (0.012 + 0.02 * rng.random())) % 1.0) * w
        py = ((rng.random() + t * (0.006 + 0.015 * rng.random())) % 1.0) * h
        rad = 0.004 * w * (0.5 + rng.random())
        a = (0.25 + 0.5 * rng.random()) * k * 255.0
        d2 = ((xx - px) ** 2 + (yy - py) ** 2) / (2.0 * rad * rad)
        g = np.exp(-d2).astype(np.float32)
        out += (g * a)[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def bokeh(fr: np.ndarray, t: float, k: float = 0.5, seed: int = 2) -> np.ndarray:
    """دوائر ضوء ناعمة (بوكيه) — بتبقي حيّة مع الوقت."""
    h, w = fr.shape[:2]
    rng = _rng(seed)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    out = fr.astype(np.float32)
    for i in range(int(9 * k + 3)):
        cx = ((rng.random() + 0.03 * t * rng.random()) % 1.0) * w
        cy = ((rng.random() - 0.02 * t * rng.random()) % 1.0) * h
        rad = 0.05 * w * (0.35 + rng.random())
        col = np.array([rng.uniform(0.6, 1.0), rng.uniform(0.6, 0.95), rng.uniform(0.7, 1.0)], np.float32)
        ring = np.exp(-(((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * rad * rad))) * (0.20 * k * 120.0)
        out += ring[:, :, None] * col[None, None, :]
    return np.clip(out, 0, 255).astype(np.uint8)


def bloom(fr: np.ndarray, k: float = 0.5) -> np.ndarray:
    """هالة نور حول المناطق الساطعة (ناعمة ورخيصة حسابيًا)."""
    f = fr.astype(np.float32)
    bright = np.clip(f - 190.0, 0, None) / 65.0
    if bright.max() <= 0.0:
        return fr
    small = bright[::4, ::4]
    for _ in range(2):                       # تنعيم بالتوسّط (بدل فلتـر ثقيل)
        small = (small + np.roll(small, 1, 0) + np.roll(small, -1, 0)
                 + np.roll(small, 1, 1) + np.roll(small, -1, 1)) / 5.0
    up = np.repeat(np.repeat(small, 4, 0), 4, 1)[:f.shape[0], :f.shape[1]]
    return np.clip(f + up * (140.0 * k), 0, 255).astype(np.uint8)


def scanlines(fr: np.ndarray, k: float = 0.35, t: float = 0.0) -> np.ndarray:
    h = fr.shape[0]
    m = (1.0 - k * 0.13 * (0.5 + 0.5 * np.sin(np.arange(h) * 0.55 + t * 6.0))).astype(np.float32)[:, None, None]
    return np.clip(fr.astype(np.float32) * m, 0, 255).astype(np.uint8)


def grain_soft(fr: np.ndarray, k: float = 0.35, seed: int = 3) -> np.ndarray:
    g = _rng(seed).normal(0.0, 1.0, fr.shape[:2]).astype(np.float32)
    return np.clip(fr.astype(np.float32) + g[:, :, None] * (7.0 * k), 0, 255).astype(np.uint8)


def vignette_soft(fr: np.ndarray, k: float = 0.6) -> np.ndarray:
    h, w = fr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx / w - 0.5) * 2) ** 2 + ((yy / h - 0.5) * 2) ** 2)
    t01 = np.clip((r - 0.35) / 0.95, 0.0, 1.0)
    m = np.clip(1.0 - (k * 0.40) * (t01 * t01 * (3.0 - 2.0 * t01)), 0.0, 1.0)
    return np.clip(fr.astype(np.float32) * m[:, :, None], 0, 255).astype(np.uint8)


def sparkle_dust(fr: np.ndarray, t: float, k: float = 0.7, seed: int = 4) -> np.ndarray:
    """لمعات صغيرة بتلمع وبتنطفى — بتدّي إحساس سحري."""
    h, w = fr.shape[:2]
    rng = _rng(seed)
    out = fr.astype(np.float32)
    for i in range(int(26 * k + 6)):
        px = ((rng.random() + 0.02 * t * (0.4 + rng.random())) % 1.0) * w
        py = ((rng.random() - 0.015 * t * (0.3 + rng.random())) % 1.0) * h
        tw = 0.5 + 0.5 * math.sin(t * (3.0 + 4.0 * rng.random()) + i)
        rad = 0.0022 * w * (0.7 + rng.random())
        yy0, yy1 = int(max(0, py - 4 * rad)), int(min(h, py + 4 * rad))
        xx0, xx1 = int(max(0, px - 4 * rad)), int(min(w, px + 4 * rad))
        if yy1 <= yy0 or xx1 <= xx0:
            continue
        ys, xs = np.mgrid[yy0:yy1, xx0:xx1].astype(np.float32)
        g = np.exp(-(((xs - px) ** 2 + (ys - py) ** 2) / (2 * rad * rad))).astype(np.float32)
        out[yy0:yy1, xx0:xx1] += (g * (250.0 * k * tw))[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)


def sweep(fr: np.ndarray, t: float, k: float = 0.6, seed: int = 5) -> np.ndarray:
    """شعاع ضوء ناعم **مايل** بيمرّ عبر الكادر (لمعة سريعة لطيفة، مش شريط)."""
    h, w = fr.shape[:2]
    prog = (t * 0.55) % 1.4 - 0.2
    cx = prog * w * 1.3
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    tilt = 0.10 * w * ((ys / max(1, h - 1)) - 0.5)
    band = np.exp(-((xs + tilt - cx) ** 2) / (2 * (0.055 * w) ** 2)).astype(np.float32)
    shade = (0.55 + 0.45 * np.exp(-(((ys / max(1, h - 1)) - 0.45) ** 2) * 4.0)).astype(np.float32)
    add = (band * shade * (72.0 * k))[:, :, None] * np.array([1.0, 0.95, 0.85], np.float32)[None, None, :]
    return np.clip(fr.astype(np.float32) + add, 0, 255).astype(np.uint8)


_FUNCS = {
    "light_leak": lambda fr, t, dur, k, pos, seed: light_leak(fr, k, "left" if (seed % 2) else "right"),
    "flare": lambda fr, t, dur, k, pos, seed: flare(fr, pos, k),
    "dust": lambda fr, t, dur, k, pos, seed: dust(fr, t, k, seed),
    "bokeh": lambda fr, t, dur, k, pos, seed: bokeh(fr, t, k, seed),
    "bloom": lambda fr, t, dur, k, pos, seed: bloom(fr, k),
    "scanlines": lambda fr, t, dur, k, pos, seed: scanlines(fr, k, t),
    "grain_soft": lambda fr, t, dur, k, pos, seed: grain_soft(fr, k, seed),
    "vignette_soft": lambda fr, t, dur, k, pos, seed: vignette_soft(fr, k),
    "sparkle_dust": lambda fr, t, dur, k, pos, seed: sparkle_dust(fr, t, k, seed),
    "sweep": lambda fr, t, dur, k, pos, seed: sweep(fr, t, k, seed),
}


def apply(frame, eff: dict, t: float, dur: float = 2.0, seed: int = 0) -> np.ndarray:
    """ينفّذ إضافة واحدة على الكادر — بظهور/اختفاء ناعم."""
    fn = _FUNCS.get(eff.get("kind"))
    if fn is None:
        return _u8(frame)
    st = float(eff.get("strength", 0.6)) * _fade(t, float(eff.get("dur", dur)) or dur)
    if st <= 0.01:
        return _u8(frame)
    return fn(_u8(frame), float(t), float(dur), st,
              tuple(eff.get("pos", (0.7, 0.3))), int(eff.get("seed", seed)))


def apply_all(frame, effs: list, t: float, seed: int = 0) -> np.ndarray:
    """يطبّق كل إضافات مقطع بالترتيب (الغبار/اللمعات بعد التوهّج أحلى) — بتحترم وقت بداية كل إضافة."""
    out = _u8(frame)
    for e in sorted(effs or [], key=lambda x: (x.get("kind") in ("bloom", "flare", "light_leak"),)):
        te = float(t) - float(e.get("at", 0.0))
        if te < 0 or te > float(e.get("dur", 2.0)) + 0.35:
            continue
        out = apply(out, e, te, seed=seed)
    return out


def catalog() -> dict:
    return {"kinds": list(KINDS), "weights": WEIGHTS,
            "note": "إضافات مولّدة بالكود — مخزون لا نهائي · بلا أي حقوق"}
