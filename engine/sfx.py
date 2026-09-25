"""
🎉 مكتبة المؤثرات الصوتية — Dollars Studio (ملكية كاملة 100%)
=============================================================
دي «الميمز الصوتية» بتاعتنا: كلها **متولّدة بالكود** (تركيب موجات) — مش مسروقة من
حد، ومفيش أي حقوق عليها. بتستخدم في: الانتقالات · اللحظات المضحكة · التأكيدات ·
المفاجآت · العدّادات — ودي اللي بتنعش الشورتس والقِصص.

الواجهة:
    from engine import sfx
    sfx.build_all("assets/sfx")            # يبني المكتبة كلها WAV
    sfx.montage("assets/sfx/preview.wav")  # ملف واحد تسمع فيه كل المؤثرات
    sfx.by_use("comedy")                   # أسماء مؤثرات الكوميديا
"""
from __future__ import annotations

import json
import math
import pathlib

import numpy as np

SR = 44100


# ───────────────────────────── أدوات تركيب ─────────────────────────────

def _t(dur: float) -> np.ndarray:
    return (np.arange(int(dur * SR), dtype=np.float32) / SR)


def _noise(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal(n).astype(np.float32) * 0.5


def _ad(t: np.ndarray, attack: float = 0.004, decay: float = 0.25, power: float = 1.0):
    """مغلّف: صعود سريع ثم تلاشي أسّي (شكل أي مؤثر حقيقي)."""
    a = np.clip(t / max(attack, 1e-4), 0.0, 1.0)
    d = np.exp(-t / max(decay, 1e-4))
    return (a * d) ** power


def _band(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """فلتر بالـ FFT (سريع ونظيف): يمرّر الترددات بين lo و hi."""
    n = x.size
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    mask = np.ones_like(f, dtype=np.float32)
    if lo > 0:
        mask *= 1.0 / (1.0 + (lo / np.maximum(f, 1e-6)) ** 4)
    if hi > 0:
        mask *= 1.0 / (1.0 + (np.maximum(f, 1e-6) / hi) ** 4)
    return np.fft.irfft(X * mask, n=n).astype(np.float32)


def _tone(freq: float, dur: float, amp: float = 0.5, shape: str = "sine",
          sweep: float | None = None) -> np.ndarray:
    t = _t(dur)
    f = np.linspace(freq, sweep, t.size, dtype=np.float32) if sweep else np.full(t.size, freq, np.float32)
    ph = 2.0 * np.pi * np.cumsum(f) / SR
    if shape == "sine":
        w = np.sin(ph)
    elif shape == "square":
        w = np.sign(np.sin(ph))
    elif shape == "saw":
        w = 2.0 * ((ph / (2 * np.pi)) % 1.0) - 1.0
    else:  # triangle
        w = 2.0 * np.abs(2.0 * ((ph / (2 * np.pi)) % 1.0) - 1.0) - 1.0
    return (w * amp).astype(np.float32)


def _fade_edges(x: np.ndarray, ms: float = 4.0) -> np.ndarray:
    k = max(2, int(SR * ms / 1000.0))
    k = min(k, x.size // 2) if x.size > 4 else 1
    if k > 1:
        ramp = np.linspace(0.0, 1.0, k, dtype=np.float32)
        x[:k] *= ramp
        x[-k:] *= ramp[::-1]
    return x


def _norm(x: np.ndarray, peak: float = 0.92) -> np.ndarray:
    m = float(np.max(np.abs(x))) if x.size else 0.0
    return (x * (peak / m)).astype(np.float32) if m > 1e-9 else x


# ───────────────────────────── المؤثرات ─────────────────────────────
# كل مؤثر: دالة بترجّع موجة mono في المدى [-1, 1]

def whoosh(dur: float = 0.55) -> np.ndarray:
    """هواء سريع — للانتقالات."""
    n = int(dur * SR)
    t = _t(dur)
    x = _noise(n, 1) * (np.sin(np.pi * t / dur) ** 1.6)
    x = _band(x, 220.0, 6000.0)
    return _norm(_fade_edges(x))


def swipe(dur: float = 0.35) -> np.ndarray:
    """مسحة قصيرة — للقطع السريع."""
    n = int(dur * SR)
    x = _noise(n, 2) * _ad(_t(dur), 0.002, dur / 4.0)
    return _norm(_fade_edges(_band(x, 900.0, 9000.0)))


def pop(dur: float = 0.14) -> np.ndarray:
    """«طقّة» فقاعة — للظهور المفاجئ."""
    x = _tone(620.0, dur, 0.7, sweep=150.0) * _ad(_t(dur), 0.001, 0.035)
    return _norm(_fade_edges(x))


def boing(dur: float = 0.55) -> np.ndarray:
    """«بوينج» كاريكاتيري — لأي وقعة مضحكة."""
    t = _t(dur)
    vib = 26.0 * np.sin(2 * np.pi * 11.0 * t) * np.exp(-t * 3.0)
    f = 180.0 * np.exp(-t * 2.2) + 60.0 + vib * 6.0
    ph = 2 * np.pi * np.cumsum(f.astype(np.float32)) / SR
    x = np.sin(ph) * np.exp(-t * 3.4)
    return _norm(_fade_edges(x))


def spring(dur: float = 0.7) -> np.ndarray:
    """سلكة بتترعش — للمفاجآت."""
    t = _t(dur)
    f = 900.0 + 700.0 * np.sin(2 * np.pi * 17.0 * t) * np.exp(-t * 2.0)
    ph = 2 * np.pi * np.cumsum(f.astype(np.float32)) / SR
    return _norm(_fade_edges(np.sin(ph) * np.exp(-t * 2.6) * 0.7))


def bubble(dur: float = 0.22) -> np.ndarray:
    """فقاعة بتطلع — للماء والسلايم."""
    t = _t(dur)
    f = 220.0 + 900.0 * (t / dur) ** 2
    ph = 2 * np.pi * np.cumsum(f.astype(np.float32)) / SR
    return _norm(_fade_edges(np.sin(ph) * _ad(t, 0.003, 0.09)))


def ding(dur: float = 0.9, base: float = 1180.0) -> np.ndarray:
    """جرس ناعم — للتأكيد."""
    x = np.zeros(int(dur * SR), np.float32)
    for k, (mul, amp, dec) in enumerate([(1.0, 0.6, 0.5), (2.01, 0.25, 0.33), (3.02, 0.12, 0.22)]):
        x += _tone(base * mul, dur, amp) * np.exp(-_t(dur) / dec)
    return _norm(_fade_edges(x))


def bell(dur: float = 1.2, base: float = 660.0) -> np.ndarray:
    """جرس أكبر — بدايات القصص."""
    x = np.zeros(int(dur * SR), np.float32)
    for mul, amp, dec in [(1.0, 0.55, 0.8), (2.76, 0.22, 0.4), (5.4, 0.1, 0.2)]:
        x += _tone(base * mul, dur, amp) * np.exp(-_t(dur) / dec)
    return _norm(_fade_edges(x))


def sparkle(dur: float = 0.8) -> np.ndarray:
    """رشّة نجوم — للسحر واللمعان."""
    x = np.zeros(int(dur * SR), np.float32)
    rng = np.random.default_rng(5)
    for i in range(14):
        st = float(rng.random() * dur * 0.7)
        f = float(rng.uniform(1600, 4200))
        seg = _tone(f, 0.12, 0.35 * (1.0 - st / dur)) * _ad(_t(0.12), 0.002, 0.03)
        j = int(st * SR)
        x[j:j + seg.size] += seg[:max(0, x.size - j)]
    return _norm(_fade_edges(x))


def magic(dur: float = 1.1) -> np.ndarray:
    """صعود سحري — لتحوّل أو حل مبهِر."""
    x = np.zeros(int(dur * SR), np.float32)
    for i, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
        st = i * 0.11
        seg = _tone(f, 0.5, 0.4) * _ad(_t(0.5), 0.004, 0.16)
        j = int(st * SR)
        x[j:j + min(seg.size, x.size - j)] += seg[:max(0, x.size - j)]
    sp = sparkle(0.9)
    n = max(x.size, sp.size)
    x = np.pad(x, (0, n - x.size)); sp = np.pad(sp, (0, n - sp.size))
    return _norm(_fade_edges(x + 0.25 * sp))


def tada(dur: float = 1.0) -> np.ndarray:
    """«تا-دا!» — للنصر."""
    x = np.zeros(int(dur * SR), np.float32)
    for st, f in ((0.0, 587.33), (0.13, 880.0)):
        seg = _tone(f, 0.75, 0.45, shape="saw") * _ad(_t(0.75), 0.006, 0.28)
        j = int(st * SR)
        x[j:j + min(seg.size, x.size - j)] += seg[:max(0, x.size - j)]
    return _norm(_fade_edges(_band(x, 120.0, 7000.0)))


def success(dur: float = 0.9) -> np.ndarray:
    """نجاح قصير — لعدّاد أو تحقّق."""
    x = np.zeros(int(dur * SR), np.float32)
    for i, f in enumerate((659.25, 830.61, 987.77)):
        seg = _tone(f, 0.35, 0.4) * _ad(_t(0.35), 0.003, 0.12)
        j = int(i * 0.09 * SR)
        x[j:j + min(seg.size, x.size - j)] += seg[:max(0, x.size - j)]
    return _norm(_fade_edges(x))


def error(dur: float = 0.5) -> np.ndarray:
    """رفة خطأ — للكوميديا (الغلطة)."""
    x = _tone(140.0, dur, 0.5, shape="square") * _ad(_t(dur), 0.003, 0.18)
    mod = 1.0 + 0.5 * np.sin(2 * np.pi * 22 * _t(dur))
    return _norm(_fade_edges(_band(x * mod, 80.0, 2500.0)))


def click(dur: float = 0.05) -> np.ndarray:
    """نقرة — للواجهة والعدادات."""
    return _norm(_fade_edges(_tone(2100.0, dur, 0.7, sweep=900.0) * _ad(_t(dur), 0.0005, 0.012)))


def tick(dur: float = 0.08) -> np.ndarray:
    """تكّة ساعة — للتوتّر أو الانتظار."""
    x = _tone(1400.0, dur, 0.5, sweep=1000.0) * _ad(_t(dur), 0.001, 0.02)
    return _norm(_fade_edges(_band(x, 600.0, 5000.0)))


def heartbeat(dur: float = 0.85) -> np.ndarray:
    """دقّة قلب — للمشهد العاطفي."""
    x = np.zeros(int(dur * SR), np.float32)
    for st, amp in ((0.0, 1.0), (0.22, 0.7)):
        seg = _tone(62.0, 0.22, amp, sweep=44.0) * _ad(_t(0.22), 0.004, 0.05)
        j = int(st * SR)
        x[j:j + min(seg.size, x.size - j)] += seg[:max(0, x.size - j)]
    return _norm(_fade_edges(x))


def thud(dur: float = 0.45) -> np.ndarray:
    """ارتطام ثقيل — للوقع."""
    t = _t(dur)
    body = _tone(70.0, dur, 0.9, sweep=34.0) * np.exp(-t / 0.12)
    ch = _noise(int(dur * SR), 7) * np.exp(-t / 0.02) * 0.5
    return _norm(_fade_edges(_band(body + ch, 25.0, 3000.0)))


def drum(dur: float = 0.35) -> np.ndarray:
    """طبلة — إيقاع للشورتس."""
    t = _t(dur)
    x = _tone(150.0, dur, 0.8, sweep=60.0) * np.exp(-t / 0.08)
    x += _noise(int(dur * SR), 9) * np.exp(-t / 0.03) * 0.35
    return _norm(_fade_edges(x))


def cymbal(dur: float = 0.9) -> np.ndarray:
    """صنجة صغيرة — للمفاجأة."""
    t = _t(dur)
    x = _noise(int(dur * SR), 11) * np.exp(-t / 0.25)
    return _norm(_fade_edges(_band(x, 3000.0, 12000.0)))


def impact(dur: float = 0.8) -> np.ndarray:
    """ضربة سينمائية — لبداية مشهد."""
    t = _t(dur)
    x = _tone(48.0, dur, 1.0, sweep=30.0) * np.exp(-t / 0.25)
    x += _band(_noise(int(dur * SR), 13) * np.exp(-t / 0.06), 60.0, 4000.0) * 0.8
    return _norm(_fade_edges(x))


def riser(dur: float = 1.6) -> np.ndarray:
    """تصعيد — قبل الذروة."""
    t = _t(dur)
    x = _noise(int(dur * SR), 17) * (t / dur) ** 2.2
    x += _tone(220.0, dur, 0.25, sweep=1800.0) * (t / dur) ** 1.5
    return _norm(_fade_edges(_band(x, 200.0, 9000.0)))


def bass_drop(dur: float = 1.3) -> np.ndarray:
    """دروب منخفض — للانتقال القوي."""
    t = _t(dur)
    x = _tone(150.0, dur, 0.95, sweep=32.0) * np.exp(-t / 0.55)
    return _norm(_fade_edges(x))


def slide_whistle(dur: float = 0.9) -> np.ndarray:
    """صفارة منزلقة — للسقوط والكوميديا."""
    t = _t(dur)
    f = 700.0 + 900.0 * np.sin(np.pi * t / dur)
    ph = 2 * np.pi * np.cumsum(f.astype(np.float32)) / SR
    return _norm(_fade_edges(np.sin(ph) * 0.8 * np.sin(np.pi * t / dur)))


def sad_trombone(dur: float = 1.5) -> np.ndarray:
    """نغمة حزينة كاريكاتيرية (تو-تو-تو-تااااا) — للفشل المضحك."""
    x = np.zeros(int(dur * SR), np.float32)
    notes = [(0.0, 0.28, 233.08), (0.30, 0.26, 220.0), (0.58, 0.24, 207.65), (0.84, 0.62, 174.61)]
    for st, ln, f in notes:
        seg = _tone(f, ln, 0.5, shape="saw") * _ad(_t(ln), 0.05, ln * 0.7)
        vib = 1.0 + 0.02 * np.sin(2 * np.pi * 5.5 * _t(ln))
        j = int(st * SR)
        n = min(seg.size, x.size - j)
        x[j:j + n] += (seg[:n] * vib[:n])
    return _norm(_fade_edges(_band(x, 120.0, 3200.0)))


def coin(dur: float = 0.4) -> np.ndarray:
    """عملة — مكافأة/نقطة."""
    x = np.zeros(int(dur * SR), np.float32)
    for st, f in ((0.0, 987.77), (0.07, 1318.5)):
        seg = _tone(f, 0.28, 0.45) * _ad(_t(0.28), 0.002, 0.14)
        j = int(st * SR)
        x[j:j + min(seg.size, x.size - j)] += seg[:max(0, x.size - j)]
    return _norm(_fade_edges(x))


def cork(dur: float = 0.3) -> np.ndarray:
    """طقّة فلين — للاحتفال."""
    t = _t(dur)
    x = _noise(int(dur * SR), 23) * np.exp(-t / 0.02) * 0.9
    x += _tone(300.0, dur, 0.5, sweep=120.0) * np.exp(-t / 0.05)
    return _norm(_fade_edges(_band(x, 150.0, 8000.0)))


def paper(dur: float = 0.6) -> np.ndarray:
    """ورق بيتقلّب — للقصص الورقية."""
    t = _t(dur)
    x = _noise(int(dur * SR), 29) * (0.3 + 0.7 * np.abs(np.sin(2 * np.pi * 6 * t)))
    return _norm(_fade_edges(_band(x, 900.0, 7000.0)))


def water(dur: float = 0.7) -> np.ndarray:
    """رشّة ماء — للسلايم والماء."""
    t = _t(dur)
    x = _noise(int(dur * SR), 31) * np.exp(-t / 0.18)
    x += _tone(900.0, dur, 0.2, sweep=300.0) * _ad(t, 0.002, 0.1)
    return _norm(_fade_edges(_band(x, 400.0, 9000.0)))


def glitch(dur: float = 0.45) -> np.ndarray:
    """تشويش رقمي — للانتقال التقني."""
    n = int(dur * SR)
    rng = np.random.default_rng(37)
    x = _noise(n, 41)
    step = 64
    q = (x * 4.0).astype(np.int32) / 4.0                      # تشويش كمّي
    gates = np.repeat(rng.integers(0, 2, n // step + 1), step)[:n]
    return _norm(_fade_edges(_band(q * gates, 300.0, 9000.0)))


def record_stop(dur: float = 0.6) -> np.ndarray:
    """توقّف مفاجئ — للكوميديا (كل حاجة وقفت)."""
    t = _t(dur)
    f = 420.0 * np.exp(-t * 6.0) + 60.0
    ph = 2 * np.pi * np.cumsum(f.astype(np.float32)) / SR
    x = (np.sin(ph) + 0.35 * _noise(int(dur * SR), 43)) * np.exp(-t / 0.22)
    return _norm(_fade_edges(_band(x, 60.0, 5000.0)))


def appear(dur: float = 0.6) -> np.ndarray:
    """ظهور/تجمّع بروح سحرية — لإدخال شخصية."""
    x = _tone(392.0, dur, 0.35, sweep=784.0) * _ad(_t(dur), 0.15, 0.25)
    return _norm(_fade_edges(x + 0.3 * bell(0.6, 784.0)))


def zoom(dur: float = 0.35) -> np.ndarray:
    """زووم سريع — للتأكيد على تفصيلة."""
    x = _tone(300.0, dur, 0.6, sweep=1400.0) * _ad(_t(dur), 0.003, dur / 3.0)
    return _norm(_fade_edges(_band(x, 150.0, 8000.0)))


# ═══════════════ الجيل الثاني: مخزون محلي إضافي (كلهم من توليفنا) ═══════════════

def shimmer(dur: float = 1.4, base: float = 880.0) -> np.ndarray:
    """لمعة معدنية صاعدة — للكشف والمفاجآت الحلوة."""
    t = _t(dur); x = np.zeros_like(t)
    for k in range(1, 9):
        x += np.sin(2 * np.pi * base * k * (1 + 0.04 * t) * t) / (k ** 1.25)
    return _norm(x * _ad(t, 0.01, dur * 0.9, 1.6))


def swell(dur: float = 2.2, base: float = 220.0) -> np.ndarray:
    """موجة صاعدة ناعمة (بناء توتر قبل اللحظة)."""
    t = _t(dur); e = np.clip(t / dur, 0, 1) ** 2.2
    x = np.sin(2 * np.pi * base * (1 + 0.9 * e) * t) * e
    return _norm(x + 0.3 * _band(_noise(t.size, 4), 200, 5000) * e)


def downlifter(dur: float = 1.0, base: float = 420.0) -> np.ndarray:
    """هبوط ناعم (نهاية المشهد/الانتقال للي بعده)."""
    t = _t(dur); e = (1 - np.clip(t / dur, 0, 1)) ** 1.4
    x = np.sin(2 * np.pi * base * (1 - 0.7 * np.clip(t / dur, 0, 1)) * t) * e
    return _norm(x)


def reverse_swell(dur: float = 1.3) -> np.ndarray:
    """زفير معاكس (بياخدك للّي جاي)."""
    n = int(dur * SR); e = np.linspace(0, 1, n) ** 2.0
    x = _band(_noise(n, 11), 300, 7000) * e + np.sin(2 * np.pi * 180 * np.arange(n) / SR) * e * 0.35
    return _fade_edges(_norm(x, 0.85))


def tape_stop(dur: float = 0.6) -> np.ndarray:
    """توقّف شريط — وقفة مضحكة مفاجئة."""
    t = _t(dur); k = np.clip(t / dur, 0, 1)
    x = np.sin(2 * np.pi * 780 * (1 - 0.92 * k) * t) * (1 - k) ** 1.5
    x += 0.25 * _band(_noise(t.size, 13), 200, 3000) * (1 - k) ** 3
    return _norm(x)


def sub_hit(dur: float = 0.85) -> np.ndarray:
    """دفعة باص عميقة (لحظة قوية)."""
    t = _t(dur); t = np.arange(int(dur * SR)) / SR
    x = np.sin(2 * np.pi * (58 * np.exp(-4.0 * t) + 30) * t) * np.exp(-5.0 * t)
    return _norm(x, 0.95)


def soft_impact(dur: float = 0.5) -> np.ndarray:
    """وقع ناعم (مش بيزعّق)."""
    t = np.arange(int(dur * SR)) / SR
    x = np.sin(2 * np.pi * 74 * t) * np.exp(-11 * t) + 0.25 * _band(_noise(t.size, 17), 90, 420) * np.exp(-9 * t)
    return _norm(x)


def chime_soft(dur: float = 1.6, base: float = 1046.5) -> np.ndarray:
    """جرس هادئ — للانتقالات الناعمة."""
    t = _t(dur)
    x = np.sin(2 * np.pi * base * t) * np.exp(-1.9 * t) \
        + 0.42 * np.sin(2 * np.pi * base * 2.756 * t) * np.exp(-3.4 * t) \
        + 0.2 * np.sin(2 * np.pi * base * 5.4 * t) * np.exp(-5.2 * t)
    return _norm(x)


def glass_tap(dur: float = 0.35) -> np.ndarray:
    """نقرة زجاج (لمس ناعم)."""
    t = _t(dur)
    x = np.sin(2 * np.pi * 1380 * t) * np.exp(-24 * t) + 0.5 * np.sin(2 * np.pi * 2620 * t) * np.exp(-30 * t)
    return _norm(x, 0.8)


def wood_tap(dur: float = 0.3, base: float = 320.0) -> np.ndarray:
    """نقرة خشب (ملصق بيظهر)."""
    t = _t(dur)
    x = np.sin(2 * np.pi * base * t) * np.exp(-26 * t) + 0.3 * _band(_noise(t.size, 19), 400, 2600) * np.exp(-35 * t)
    return _norm(x, 0.85)


def vinyl(dur: float = 2.0) -> np.ndarray:
    """طقطقة أسطوانة قديمة (دفء/حنين)."""
    x = _noise(int(dur * SR), 23) * 0.35
    clicks = np.zeros_like(x)
    rng = np.random.default_rng(23)
    idx = rng.integers(0, x.size, max(1, int(dur * 26)))
    clicks[idx] = rng.uniform(0.3, 1.0, idx.size)
    return _norm(_band(x + clicks, 400, 6000), 0.55)


def fire_crackle(dur: float = 2.4) -> np.ndarray:
    """طقطقة نار (دفء المدفأة)."""
    rng = np.random.default_rng(29); n = int(dur * SR)
    x = _band(_noise(n, 29), 60, 900) * 0.55
    pops = np.zeros(n)
    idx = rng.integers(0, n, max(1, int(dur * 18)))
    pops[idx] = rng.uniform(0.4, 1.0, idx.size)
    return _norm(x + _band(pops, 300, 7000) * 0.9, 0.7)


def wind_gust(dur: float = 2.6) -> np.ndarray:
    """هبّة هوا (مشهد طبيعة)."""
    n = int(dur * SR); e = np.sin(np.linspace(0, np.pi, n)) ** 1.5
    x = _band(_noise(n, 31), 80, 1400) * e
    return _norm(x, 0.75)


def page_turn(dur: float = 0.45) -> np.ndarray:
    """تقليب صفحة (قِصص)."""
    n = int(dur * SR); e = np.sin(np.linspace(0, np.pi, n)) ** 1.2
    x = _band(_noise(n, 37), 900, 9000) * e * (1 + np.sign(np.linspace(-1, 1, n)) * 0.4)
    return _norm(x, 0.8)


def match_strike(dur: float = 0.5) -> np.ndarray:
    """ولاعة/عود كبريت (لحظة ضوء)."""
    n = int(dur * SR); x = _band(_noise(n, 41), 1500, 9000) * np.exp(-np.linspace(0, 9, n))
    x[: int(0.05 * SR)] *= np.linspace(0.2, 1.0, int(0.05 * SR))
    return _norm(x, 0.85)


def coin_drop(dur: float = 0.7) -> np.ndarray:
    """عملة بتقع (مكافأة)."""
    t = _t(dur)
    x = (np.sin(2 * np.pi * 1850 * t) * np.exp(-18 * t) + np.sin(2 * np.pi * 2450 * t) * np.exp(-22 * t)
         + np.sin(2 * np.pi * 3100 * t) * np.exp(-26 * t) * 0.6)
    return _norm(x, 0.85)


def ui_open(dur: float = 0.35) -> np.ndarray:
    t = _t(dur); k = np.clip(t / dur, 0, 1)
    x = np.sin(2 * np.pi * (500 + 900 * k) * t) * (1 - k) ** 1.2
    return _norm(x, 0.7)


def ui_close(dur: float = 0.35) -> np.ndarray:
    t = _t(dur); k = np.clip(t / dur, 0, 1)
    x = np.sin(2 * np.pi * (1400 - 900 * k) * t) * (1 - k) ** 1.2
    return _norm(x, 0.7)


def ui_tick(dur: float = 0.09) -> np.ndarray:
    t = _t(dur)
    return _norm(np.sin(2 * np.pi * 2100 * t) * np.exp(-40 * t), 0.6)


def whoosh_soft(dur: float = 0.9) -> np.ndarray:
    """هوّاء ناعم (انتقال بلا إزعاج)."""
    n = int(dur * SR); e = np.sin(np.linspace(0, np.pi, n)) ** 0.8
    x = _band(_noise(n, 43), 200, 3200) * e
    return _norm(x, 0.7)


def beam(dur: float = 1.1, base: float = 523.25) -> np.ndarray:
    """شعاع ضوء/سحر صاعد."""
    t = _t(dur); e = np.clip(t / dur, 0, 1)
    x = np.sin(2 * np.pi * base * (1 + 1.6 * e) * t) * (1 - e) ** 0.8
    return _norm(x)


def lullaby_note(dur: float = 1.8, base: float = 659.25) -> np.ndarray:
    """نغمة تهويدة واحدة (قِصص النوم)."""
    t = _t(dur)
    x = np.sin(2 * np.pi * base * t) * np.exp(-2.1 * t) + 0.3 * np.sin(2 * np.pi * base * 2 * t) * np.exp(-3.4 * t)
    return _norm(x, 0.75)


def magic_up(dur: float = 1.2, base: float = 392.0) -> np.ndarray:
    """صعود سحري (تحوّل/اكتشاف)."""
    t = _t(dur); k = np.clip(t / dur, 0, 1)
    x = sum(np.sin(2 * np.pi * base * (1.5 ** j) * (1 + 0.5 * k) * t) / (j + 2) for j in range(5)) * (1 - k * 0.6)
    return _norm(x)


def warm_hum(dur: float = 2.5, base: float = 110.0) -> np.ndarray:
    """طنين دافئ (خلفية قِصة)."""
    t = _t(dur)
    x = np.sin(2 * np.pi * base * t) + 0.5 * np.sin(2 * np.pi * base * 2 * t) + 0.25 * np.sin(2 * np.pi * base * 3 * t)
    x *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.35 * t)
    return _fade_edges(x) / (np.abs(_fade_edges(x)).max() + 1e-9) * 0.75


def thunder_far(dur: float = 3.2) -> np.ndarray:
    """رعد بعيد (بلا خضّة)."""
    n = int(dur * SR); t = np.arange(n) / SR
    e = np.exp(-np.linspace(0, 3.4, n))
    x = _band(_noise(n, 47), 25, 260) * e + 0.4 * np.sin(2 * np.pi * 42 * t) * e
    return _norm(_fade_edges(x), 0.7)


def rain_drop(dur: float = 0.28) -> np.ndarray:
    """قطرة مطر واحدة على سطح."""
    t = _t(dur)
    x = np.sin(2 * np.pi * (900 + 1400 * np.clip(t / dur, 0, 1)) * t) * np.exp(-30 * t)
    return _norm(x, 0.7)


def bubble_pop(dur: float = 0.22) -> np.ndarray:
    t = _t(dur); k = np.clip(t / dur, 0, 1)
    x = np.sin(2 * np.pi * (260 + 900 * k * k) * t) * np.exp(-16 * t)
    return _norm(x, 0.8)


def twinkle_run(dur: float = 1.6) -> np.ndarray:
    """جَرْية لمعات صاعدة (مرح)."""
    out = np.zeros(int(dur * SR), np.float32)
    notes = [784, 880, 1046.5, 1174.7, 1318.5, 1568]
    step = dur / len(notes)
    for i, f in enumerate(notes):
        seg = int(step * SR); t = np.arange(seg) / SR
        y = np.sin(2 * np.pi * f * t) * np.exp(-9 * t) * 0.5
        j = int(i * step * SR); m = min(seg, out.size - j)
        out[j:j + m] += y[:m]
    return _norm(out, 0.8)


SFX = {
    # انتقالات
    "whoosh": whoosh, "swipe": swipe, "zoom": zoom, "glitch": glitch,
    "riser": riser, "bass_drop": bass_drop, "impact": impact, "record_stop": record_stop,
    # كوميديا
    "boing": boing, "spring": spring, "slide_whistle": slide_whistle,
    "sad_trombone": sad_trombone, "error": error, "bubble": bubble, "pop": pop,
    # مفاجآت وفرح
    "tada": tada, "magic": magic, "sparkle": sparkle, "coin": coin, "cork": cork,
    "appear": appear, "cymbal": cymbal, "success": success,
    # عالم ومشاهد
    "thud": thud, "drum": drum, "heartbeat": heartbeat, "tick": tick,
    "water": water, "paper": paper, "click": click, "ding": ding, "bell": bell,
    # الجيل الثاني (مخزون محلي إضافي)
    "shimmer": shimmer, "swell": swell, "downlifter": downlifter, "reverse_swell": reverse_swell,
    "tape_stop": tape_stop, "sub_hit": sub_hit, "soft_impact": soft_impact, "chime_soft": chime_soft,
    "glass_tap": glass_tap, "wood_tap": wood_tap, "vinyl": vinyl, "fire_crackle": fire_crackle,
    "wind_gust": wind_gust, "page_turn": page_turn, "match_strike": match_strike, "coin_drop": coin_drop,
    "ui_open": ui_open, "ui_close": ui_close, "ui_tick": ui_tick, "whoosh_soft": whoosh_soft,
    "beam": beam, "lullaby_note": lullaby_note, "magic_up": magic_up, "warm_hum": warm_hum,
    "thunder_far": thunder_far, "rain_drop": rain_drop, "bubble_pop": bubble_pop, "twinkle_run": twinkle_run,
}

USES = {
    "transition": ["whoosh", "swipe", "zoom", "glitch", "riser", "bass_drop", "impact", "record_stop"],
    "comedy": ["boing", "spring", "slide_whistle", "sad_trombone", "error", "bubble", "pop"],
    "celebration": ["tada", "magic", "sparkle", "coin", "cork", "appear", "cymbal", "success"],
    "world": ["thud", "drum", "heartbeat", "tick", "water", "paper", "click", "ding", "bell"],
    "atmosphere": ["vinyl", "fire_crackle", "wind_gust", "thunder_far", "rain_drop", "warm_hum"],
    "magic": ["shimmer", "swell", "beam", "magic_up", "twinkle_run", "reverse_swell", "downlifter"],
    "ui_soft": ["ui_open", "ui_close", "ui_tick", "glass_tap", "wood_tap", "coin_drop", "page_turn",
                "match_strike", "bubble_pop", "chime_soft", "lullaby_note", "whoosh_soft", "soft_impact",
                "sub_hit", "tape_stop"],
}

# الأنسب لكل نوع فيديو (يستخدمه المجمّع تلقائيًا)
RECOMMENDED = {
    "sleep": [],
    "story": ["bell", "appear", "boing", "sparkle", "magic", "slide_whistle", "sad_trombone", "tada",
              "chime_soft", "lullaby_note", "beam", "page_turn", "magic_up", "twinkle_run", "warm_hum",
              "glass_tap", "wood_tap", "rain_drop", "match_strike"],
    "satisfying": ["bubble", "pop", "click", "sparkle", "ding", "swipe",
                   "ui_tick", "glass_tap", "wood_tap", "coin_drop", "bubble_pop", "shimmer", "whoosh_soft",
                   "soft_impact", "ui_open", "ui_close"],
    "short_comedy": ["boing", "spring", "record_stop", "error", "slide_whistle", "whoosh", "pop",
                     "tape_stop", "sub_hit", "downlifter", "vinyl", "swell", "reverse_swell"],
}


# ───────────────────────────── الواجهات ─────────────────────────────

def render(name: str) -> np.ndarray:
    if name not in SFX:
        raise KeyError(f"مؤثر غير معروف: {name} (المتاح: {', '.join(sorted(SFX))})")
    return _norm(SFX[name]())


def write_wav(path, x: np.ndarray, sr: int = SR) -> pathlib.Path:
    import wave
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(x, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def build_all(out_dir="assets/sfx") -> list:
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for name in sorted(SFX):
        made.append(write_wav(out / f"{name}.wav", render(name)))
    index = {
        "note": "مكتبة مؤثرات Dollars — متولّدة بالكود 100%، ملكية كاملة، بلا أي حقوق غيرنا.",
        "license": "owned-generated",
        "sample_rate": SR,
        "count": len(SFX),
        "uses": USES,
        "recommended": RECOMMENDED,
        "files": {n: f"{n}.wav" for n in sorted(SFX)},
    }
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return made


def montage(path="assets/sfx/preview.wav", gap: float = 0.35) -> pathlib.Path:
    """ملف واحد فيه كل المؤثرات بالترتيب — تسمعه كله في دقيقة."""
    chunks = []
    for name in sorted(SFX):
        chunks.append(render(name))
        chunks.append(np.zeros(int(gap * SR), np.float32))
    return write_wav(path, np.concatenate(chunks))


def by_use(kind: str) -> list:
    if kind not in USES:
        raise KeyError(f"استخدام غير معروف: {kind} (المتاح: {', '.join(USES)})")
    return list(USES[kind])


def summary() -> str:
    lines = [f"🎉 مكتبة المؤثرات: {len(SFX)} مؤثر · ملكية كاملة 100%"]
    for kind, names in USES.items():
        lines.append(f"  • {kind}: {' · '.join(names)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
    build_all()
    montage()
    print("✅ اتبنت المكتبة في assets/sfx")
