"""🎧 مولّد الأجواء الصوتية — ملكية كاملة 100% (صفر حقوق · صفر Content ID).

ليه بنولّد الصوت بالكود بدل ما ننزّل مقاطع؟
  • أي مقطع صوتي من أي مكان = مخاطرة مطالبة حقوق (Content ID بيمسك حتى 3 ثواني).
  • الصوت المولّد بالكود = ملكنا للأبد، وممكن نطوّله لأي مدة (8 ساعات و24 ساعة).
  • وبيبقى **قابل للتكرار الحلقي** (loop) بشكل مثالي = فيديوهات نوم ما فيها قطع.

الفنيّة: توليد بالبلوكات + فلترة في نطاق الترددات (FFT) = سرعة عالية وذاكرة صغيرة،
عشان نقدر نطلّع ساعات صوت من GitHub Actions (بلا GPU وبذاكرة محدودة).
"""
from __future__ import annotations

import math
import pathlib
import wave

import numpy as np

SR = 44100          # معدل العينات القياسي
BLOCK = 20.0        # طول البلوك بالثواني (توليد بالتدريج = ذاكرة صغيرة)
XFADE = 2.0         # تداخل ناعم بين البلوكات (منع أي طقطقة)
RNG = np.random.default_rng()


# ───────────────────────── أدوات أساسية ─────────────────────────

def _n(seconds: float) -> int:
    return int(SR * seconds)


def _band(x: np.ndarray, lo: float, hi: float, roll: float = 2.0) -> np.ndarray:
    """فلترة نطاقية في مجال الترددات: نمرّر نطاق [lo, hi] وننعّم الحواف.

    أسرع آلاف المرات من أي حلقة IIR في بايثون، ونفس النتيجة السماعية.
    """
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(x.size, 1.0 / SR)
    with np.errstate(divide="ignore"):
        mask = 1.0 / (1.0 + (f / max(hi, 1.0)) ** (2 * roll))
        mask *= 1.0 / (1.0 + (max(lo, 1.0) / np.maximum(f, 1e-6)) ** (2 * roll))
    out = np.fft.irfft(spec * mask, n=x.size)
    return out.astype(np.float32)


def _color(seconds: float, alpha: float = 1.0) -> np.ndarray:
    """ضجيج ملوّن: alpha=0 أبيض · 1 وردي · 2 بنّي (الطبيعة صوتها ملوّن مش أبيض)."""
    x = RNG.standard_normal(_n(seconds)).astype(np.float32)
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(x.size, 1.0 / SR)
    f[0] = f[1] if f.size > 1 else 1.0
    out = np.fft.irfft(spec / (f ** alpha), n=x.size)
    m = float(np.max(np.abs(out))) or 1.0
    return (out / m).astype(np.float32)


def _env(seconds: float, rate: float = 0.07, smooth: int = 64) -> np.ndarray:
    """منحنى شدة بطيء (تنفّس): بيدي إحساس إن الصوت «حي» مش ثابت ممل."""
    n = _n(seconds)
    m = max(8, int(seconds * rate))
    smooth = max(1, min(int(smooth), m))       # نضمن إن طول الخرج = m بالظبط
    e = RNG.random(m).astype(np.float32)
    e = np.convolve(e, np.ones(smooth, np.float32) / smooth, mode="same")
    e = 0.55 + 0.45 * (e - e.min()) / max(1e-6, (e.max() - e.min()))
    return np.interp(np.linspace(0, m - 1, n), np.arange(m), e).astype(np.float32)


def _impulses(seconds: float, rate_hz: float, low: float, high: float,
              decay: tuple[float, float], gain: float) -> np.ndarray:
    """نبضات عشوائية (قطرات/طقطقة/فروع شجر) بمصادر نقطية + صدى قصير."""
    n = _n(seconds)
    out = np.zeros(n, dtype=np.float32)
    count = max(1, int(rate_hz * seconds))
    pos = RNG.integers(0, n, count)
    for p in pos:
        d = float(RNG.uniform(*decay))
        ln = min(_n(d), n - p)
        if ln <= 2:
            continue
        t = np.arange(ln, dtype=np.float32) / SR
        f0 = float(RNG.uniform(low, high))
        # هجوم 3ms: بيمنع «الطقّة» المعدنية من بداية الموجة الحادة
        env = ((1.0 - np.exp(-t / 0.003)) * np.exp(-t / (d / 3.2))).astype(np.float32)
        tone = np.sin(2 * math.pi * f0 * t).astype(np.float32)
        out[p:p + ln] += env * tone
    if count:
        out *= gain / max(1e-6, float(np.max(np.abs(out))))
    return out


# ───────────────────────── الأصوات (كل واحد دالة) ─────────────────────────

def rain(seconds: float, heavy: float = 0.5) -> np.ndarray:
    """مطر: نطاق عالي مستمر + طبقة «على الزجاج» + قطرات نقطية."""
    base = _band(_color(seconds, 0.9), 400, 9000, 1.2) * 0.55
    body = _band(_color(seconds, 1.6), 80, 600, 1.0) * (0.20 + 0.35 * heavy)
    drops = _impulses(seconds, 55 * (0.5 + heavy), 900, 4200,
                      (0.02, 0.09), 0.35)
    glass = _impulses(seconds, 14 * (0.4 + heavy), 400, 1400, (0.05, 0.16), 0.25)
    mix = base * _env(seconds, 0.05) + body + drops + glass
    return _norm(mix, 0.72)


def thunder(seconds: float, distance: float = 0.5) -> np.ndarray:
    """رعد: هدير منخفض طويل + فرقعة قريبة (المسافة بتغيّر اللون)."""
    rumble = _band(_color(seconds, 2.0), 18, 140, 1.4)
    t = np.arange(rumble.size, dtype=np.float32) / SR
    strike = float(RNG.uniform(0.05, 0.35)) * seconds
    env = np.zeros_like(t)
    start = int(strike * SR)
    env[start:] = np.exp(-np.arange(t.size - start, dtype=np.float32)
                         / (SR * (2.2 + 3.0 * (1 - distance))))
    crack = _band(_color(seconds, 1.1), 60, 1200, 1.0) * env * (0.9 - 0.6 * distance)
    mix = rumble * env * (0.7 + 0.5 * (1 - distance)) + crack
    return _norm(mix, 0.75)


def wind(seconds: float) -> np.ndarray:
    """ريح: ضجيج منخفض بمنحنى تنفّس + صفير خفيف وقت القوة."""
    base = _band(_color(seconds, 1.8), 40, 900, 1.3)
    whistle = _band(_color(seconds, 1.2), 700, 2600, 1.1)
    e = _env(seconds, 0.03, 128)
    mix = base * e + whistle * np.clip(e - 0.75, 0, 1) * 1.6
    return _norm(mix, 0.62)


def waves(seconds: float, period: float = 9.0) -> np.ndarray:
    """موج بحر: نطاق منخفض + منحنى مدّ وجزر منتظم + رغوة."""
    n = _n(seconds)
    t = np.arange(n, dtype=np.float32) / SR
    swell = (0.45 + 0.55 * (0.5 + 0.5 * np.sin(2 * math.pi * t / period))
             * (0.7 + 0.3 * np.sin(2 * math.pi * t / (period * 3.1) + 1.2)))
    body = _band(_color(seconds, 1.7), 60, 1200, 1.2) * swell
    foam = _band(_color(seconds, 0.9), 2000, 8000, 1.1) * np.clip(swell - 0.75, 0, 1) * 2.2
    return _norm(body + foam, 0.68)


def fire(seconds: float) -> np.ndarray:
    """نار/مدفأة: همهمة منخفضة + طقطقات عشوائية دافية."""
    hum = _band(_color(seconds, 1.6), 50, 700, 1.2) * 0.35
    crackle = _impulses(seconds, 26, 600, 5200, (0.008, 0.05), 0.5)
    return _norm(hum * _env(seconds, 0.15, 96) + crackle, 0.6)


def brown_sleep(seconds: float) -> np.ndarray:
    """ضجيج بنّي عميق للنوم (الأكثر مشاهدة على يوتيوب: 378 مليون مشاهدة)."""
    x = _band(_color(seconds, 2.0), 12, 420, 1.5)
    return _norm(x * _env(seconds, 0.02, 256), 0.6)


def room_tone(seconds: float) -> np.ndarray:
    """همهمة غرفة هادئة — بتخلي أي سكوت يبان «حياة» مش «توقف»."""
    x = _band(_color(seconds, 1.9), 25, 320, 1.2)
    return _norm(x * 0.5, 0.28)


def heartbeat(seconds: float, bpm: float = 62) -> np.ndarray:
    """نبضات قلب هادئة (للتنفّس/التأمل) — إيقاع مضبوط وبطيء."""
    n = _n(seconds)
    out = np.zeros(n, dtype=np.float32)
    step = int(SR * 60.0 / bpm)
    for p in range(0, n - step, step):
        for off, g in ((0, 1.0), (int(0.16 * SR), 0.6)):     # نبضة + نبضة ثانية
            st = p + off
            ln = min(_n(0.22), n - st)
            if ln <= 4:
                continue
            t = np.arange(ln, dtype=np.float32) / SR
            env = np.exp(-t / 0.055).astype(np.float32)
            out[st:st + ln] += env * np.sin(2 * math.pi * 48 * t) * g
    return _norm(out, 0.55)


VOICES = {
    "rain": rain, "thunder": thunder, "wind": wind, "waves": waves,
    "fire": fire, "brown_sleep": brown_sleep, "room_tone": room_tone,
    "heartbeat": heartbeat,
}


# ───────────────────────── الخلط والتجميع ─────────────────────────

def _norm(x: np.ndarray, peak: float) -> np.ndarray:
    m = float(np.max(np.abs(x))) or 1.0
    return (x / m * peak).astype(np.float32)


def _xfade_append(buffer: np.ndarray, block: np.ndarray) -> np.ndarray:
    """يدمج بلوك جديد مع آخر XFADE ثانية من اللي قبله (تجميع ناعم بلا طقطقة)."""
    k = min(_n(XFADE), block.size, buffer.size)
    if k <= 1:
        return np.concatenate([buffer, block])
    ramp = np.linspace(0.0, 1.0, k, dtype=np.float32)
    head = buffer[:-k].copy()
    joined = buffer[-k:] * (1 - ramp) + block[:k] * ramp
    return np.concatenate([head, joined, block[k:]])


def build_track(layers: list[tuple[str, float]], seconds: float,
                master: float = 0.9) -> np.ndarray:
    """يبني مسار مونو من طبقات (اسم الصوت، شدته) لمدة ثواني.

    التوليد بلوكات (BLOCK ثانية لكل بلوك) + فلترة FFT = ساعات صوت بذاكرة صغيرة.
    """
    total = _n(seconds)
    out = np.zeros(total, dtype=np.float32)
    for name, gain in layers:
        fn = VOICES.get(name)
        if fn is None:
            raise KeyError(f"صوت غير معروف: {name}")
        acc = np.zeros(total, dtype=np.float32)
        k = _n(XFADE)
        pos = 0
        pending: np.ndarray | None = None      # آخر k عينة لسه ما اتكتبتش
        while pos < total:
            # نولّد زيادة k عينة: دول اللي هيتلحموا مع البلوك الجاي
            gen = min(_n(BLOCK) + (k if pending is not None else 0),
                      total - pos + k)
            if gen <= k:
                break
            blk = (fn(gen / SR) * float(gain)).astype(np.float32)
            if blk.size < gen:
                blk = np.pad(blk, (0, gen - blk.size))
            blk = blk[:gen].copy()
            if pending is not None:
                # ⚠️ الوصل الصح: آخر k عينة *المحجوزة* تتلحم مع أول k من الجديد.
                # (الطريقة القديمة كانت بتكتب الذيل الأول ثم تلحم بعده = طقّة)
                ramp = np.linspace(0.0, 1.0, k, dtype=np.float32)
                blk[:k] = pending * (1 - ramp) + blk[:k] * ramp
            piece = blk[:gen - k]
            take = min(piece.size, total - pos)
            acc[pos:pos + take] = piece[:take]
            pending = blk[gen - k:].copy()
            pos += take
        if pending is not None and pos < total:      # أمان أخير
            take = min(pending.size, total - pos)
            acc[pos:pos + take] = pending[:take]
        out += acc
    return _norm(out, master)


def seamless_loop(x: np.ndarray, fade: float = 6.0) -> np.ndarray:
    """يخلي المقطع ملفوف على نفسه (نهايته تكمّل بدايته) — مفتاح فيديوهات النوم."""
    k = min(_n(fade), x.size // 3)
    if k <= 1:
        return x
    ramp = np.linspace(0.0, 1.0, k, dtype=np.float32)
    loop = x[:-k].copy()
    loop[:k] = x[-k:] * (1 - ramp) + x[:k] * ramp
    return loop


def write_wav(path: pathlib.Path, mono: np.ndarray, sr: int = SR) -> pathlib.Path:
    """يكتب WAV ستيريو (نفس القناة + اختلاف صغير = إحساس مسرحي واسع)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    delay = int(0.012 * sr)                    # تأخير بسيط = عرض مسرحي
    left = mono
    right = np.concatenate([np.zeros(delay, np.float32), mono[:-delay]]) * 0.98
    stereo = np.stack([left, right], axis=1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def make(kind: str, seconds: float, out: pathlib.Path,
         loop: bool = True) -> pathlib.Path:
    """واجهة سريعة: نوع الأجواء → ملف WAV جاهز للدمج."""
    recipes = {
        "sleep_rain": [("rain", 0.85), ("thunder", 0.35), ("room_tone", 0.5)],
        "rain_only": [("rain", 1.0), ("room_tone", 0.35)],
        "ocean": [("waves", 1.0), ("wind", 0.25)],
        "storm": [("rain", 1.0), ("thunder", 0.8), ("wind", 0.5)],
        "fireplace": [("fire", 1.0), ("room_tone", 0.3)],
        "focus": [("brown_sleep", 0.85), ("wind", 0.18)],
        "calm_night": [("wind", 0.6), ("room_tone", 0.6), ("brown_sleep", 0.35)],
        "meditation": [("heartbeat", 0.5), ("room_tone", 0.5), ("wind", 0.2)],
    }
    layers = recipes.get(kind)
    if layers is None:
        raise KeyError(f"وصفة غير معروفة: {kind} (المتاح: {', '.join(recipes)})")
    # نولّد أطول بمقدار التلاشي ثم نلفّه، فنحصل على المدة المطلوبة بالظبط.
    # (شرط رياضي: التلاشي ≤ نصف المدة، وإلا طول الخرج يقلّ عن المطلوب)
    fade = min(6.0, max(0.5, seconds / 2)) if loop else 0.0
    track = build_track(layers, seconds + fade)
    if loop:
        track = seamless_loop(track, fade=fade)
    return write_wav(out, track)


if __name__ == "__main__":                     # فحص سريع
    import argparse
    ap = argparse.ArgumentParser(description="مولّد الأجواء الصوتية")
    ap.add_argument("kind")
    ap.add_argument("seconds", type=float)
    ap.add_argument("out", type=pathlib.Path)
    a = ap.parse_args()
    p = make(a.kind, a.seconds, a.out)
    print("✅", p, f"({p.stat().st_size/1e6:.1f} MB)")
