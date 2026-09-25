"""
🎵 محرّك الموسيقى — Dollars Studio
==================================
موسيقى **بنعملها بأنفسنا** (توليف رقمي بالكود) — مفيش تراك من حد، مفيش حقوق، ومفيش ملفات كبيرة:
المخزون بيتولّد وقت الطلب. كل مقطع **حلقة مقفولة بلا قطع** (نقطعه ونكرّره زي ما نحب).

    from engine import music
    x = music.bed("music_box", 40.0)        # مصفوفة (n, 2) على 44.1kHz
    styles = music.STYLES()

الأنماط: music_box · lullaby_bell · warm_pad · lofi_keys · dream_pulse · night_drone
"""
from __future__ import annotations

import math

import numpy as np

SR = 44100
TARGET_RMS = 0.075          # مستوى ثابت لكل الأنماط (بلا ما تفرقع)

# سلالم ومقامات هادية (نغمات بنستخدمها)
_MINOR = [0, 2, 3, 5, 7, 8, 10]          # سلم مينور طبيعي
_MAJOR = [0, 2, 4, 5, 7, 9, 11]
_PROGS = {                                # تتابعات كوردات (درجات من السلم)
    "calm": [0, 5, 3, 4],
    "warm": [0, 3, 4, 0],
    "hope": [0, 4, 5, 3],
    "night": [0, 2, 5, 4],
}


def _n(seconds: float) -> int:
    return int(round(seconds * SR))


def _note(freq: float, t: np.ndarray, shape: str = "sine", detune: float = 0.0) -> np.ndarray:
    w = 2 * math.pi * freq * t
    if shape == "sine":
        return np.sin(w)
    if shape == "tri":
        return 2.0 / math.pi * np.arcsin(np.sin(w))
    if shape == "soft_saw":                       # سنّ منشوري مُنعَّم (طقطقة أقل)
        x = np.zeros_like(t)
        for h in range(1, 9):
            x += np.sin(w * h) / (h ** 1.6)
        return x * 0.5
    if shape == "bell":                            # جرس: نغمات توافقية (FM بسيط)
        return np.sin(w) * np.exp(-1.5 * t * 0.35) + 0.45 * np.sin(2.76 * w) * np.exp(-3.0 * t * 0.5) \
            + 0.25 * np.sin(5.4 * w) * np.exp(-5.0 * t * 0.6)
    if shape == "pluck":
        return np.sin(w) * np.exp(-6.0 * t) + 0.3 * np.sin(2 * w) * np.exp(-9.0 * t)
    return np.sin(w + detune * np.sin(2 * math.pi * 0.9 * t) * 3.0)


def _env(n: int, a: float, d: float, s: float, r: float, sus: float = 0.7) -> np.ndarray:
    """غلاف ADSR بالعينات."""
    na, nd, nr = _n(a), _n(d), _n(r)
    ns = max(0, n - na - nd - nr)
    parts = [np.linspace(0, 1, max(na, 1), dtype=np.float32),
             np.linspace(1, sus, max(nd, 1), dtype=np.float32),
             np.full(max(ns, 1), sus, dtype=np.float32),
             np.linspace(sus, 0, max(nr, 1), dtype=np.float32)]
    e = np.concatenate(parts)[:n]
    return np.pad(e, (0, max(0, n - e.size))).astype(np.float32)


def _pad(n: int, freq: float, detune: float = 1.6) -> np.ndarray:
    """طبقة دافئة: 3 أقواس بميل بسيط."""
    t = np.arange(n, dtype=np.float32) / SR
    out = np.zeros(n, np.float32)
    for k, det in enumerate((-detune, 0.0, detune)):
        f = freq * (2 ** (det / 1200.0))
        out += _note(f, t, "soft_saw") * (1.0 if k == 1 else 0.6)
    lfo = 1.0 + 0.12 * np.sin(2 * math.pi * 0.17 * t)          # تنفّس
    return (out / 2.2 * lfo).astype(np.float32)


def _midi(semi: int) -> float:
    return 440.0 * (2 ** ((semi - 9) / 12.0))


def _seamless(x: np.ndarray, xfade: float = 1.2) -> np.ndarray:
    """نقفل الحلقة: ناخد ذيل المقطع نخلطه على أوله ⇒ تكرار بلا قطع."""
    n = x.shape[0]
    k = min(_n(xfade), n // 3)
    if k <= 8:
        return x
    fade = np.linspace(0.0, 1.0, k, dtype=np.float32)[:, None]
    head = x[:k].copy()
    tail = x[n - k:].copy()
    x = x[:n - k].copy()
    x[:k] = tail * (1.0 - fade[:, 0:1]) + head * fade[:, 0:1]
    return x


XFADE = 1.4                    # طول خلط القفل (ثانية)


def bed(style: str = "warm_pad", seconds: float = 40.0, key: str = "calm",
        seed: int = 7) -> np.ndarray:
    """
    مقطع موسيقي كامل بالطول المطلوب **بالظبط** (n, 2) — هادي، متكرر بلا قطع، ومن صنعنا.
    بنولّد 1.4 ث زيادة ونقصّهم في القفل ⇒ الطول مضبوط والحلقة مقفولة في نفس الوقت.
    """
    rng = np.random.default_rng(int(seed) & 0x7FFFFFFF)
    want = _n(seconds)
    n = want + _n(XFADE)                               # طول التوليد (والقفل بيرجّعه للطول المطلوب)
    gen = seconds + XFADE
    t = np.arange(n, dtype=np.float32) / SR
    prog = _PROGS.get(key, _PROGS["calm"])
    scale = _MINOR if key in ("calm", "night") else _MAJOR
    root = 48 + int(rng.integers(0, 3))                    # C3..D3
    bar = max(2.0, seconds / 8.0)                          # شريط منطقيًا ~ ثانيتين+

    left = np.zeros(n, np.float32)
    right = np.zeros(n, np.float32)

    # ── أرضية الأكوردات ──
    if style in ("warm_pad", "night_drone", "dream_pulse"):
        for b in range(int(math.ceil(gen / bar))):
            deg = prog[b % len(prog)]
            start = _n(b * bar)
            seg = min(n - start, _n(bar + 0.6))
            if seg <= 32:
                break
            for semi in (scale[deg % 7], scale[(deg + 2) % 7] + 12, scale[(deg + 4) % 7]):
                f = _midi(root + semi)
                p = _pad(seg, f)[:seg]
                env = _env(seg, 0.8, 0.6, 0.4, 0.7, sus=0.8)
                left[start:start + seg] += p * env * 0.42
                right[start:start + seg] += p * env * 0.42
            mix = 0.5 + 0.5 * np.sin(2 * math.pi * b / max(len(prog), 1))
            del mix

    # ── لحن علوي (جرس/صندوق موسيقى) ──
    if style in ("music_box", "lullaby_bell", "dream_pulse", "lofi_keys"):
        shape = {"music_box": "pluck", "lullaby_bell": "bell", "dream_pulse": "sine",
                 "lofi_keys": "tri"}[style]
        step = bar / 4.0 if style != "dream_pulse" else bar / 3.0
        k = 0
        pos = 0.0
        while pos < gen - 0.1:
            deg = int(rng.integers(0, 7))
            semi = scale[deg] + (12 if rng.random() < 0.45 else 0) + (12 if rng.random() < 0.12 else 0)
            f = _midi(root + 12 + semi)
            dur = step * (1.4 if style != "lofi_keys" else 2.2)
            seg = _n(min(dur, gen - pos))
            if seg > 16:
                tt = np.arange(seg, dtype=np.float32) / SR
                tone = _note(f, tt, shape)
                env = _env(seg, 0.006, 0.25, 0.0, dur * 0.6, sus=0.45)
                amp = (0.30 if style == "music_box" else 0.24) * (0.7 + 0.5 * rng.random())
                pan = float(rng.uniform(-0.35, 0.35))
                l = tone * env * amp * (1.0 - max(0.0, pan))
                r = tone * env * amp * (1.0 + min(0.0, pan))
                j = _n(pos)
                left[j:j + seg] += l[:seg]
                right[j:j + seg] += r[:seg]
            pos += step
            k += 1
            if k > 4000:
                break

    # ── نبض ناعم (درام خفيف بالكود) ──
    if style in ("dream_pulse", "lofi_keys"):
        beat = bar / 2.0
        p = 0.0
        while p < gen - 0.05:
            seg = _n(0.28)
            j = _n(p)
            if j + seg < n:
                tt = np.arange(seg, dtype=np.float32) / SR
                kick = np.sin(2 * math.pi * (52.0 * np.exp(-9 * tt) + 34.0) * tt) * np.exp(-7.0 * tt) * 0.22
                left[j:j + seg] += kick
                right[j:j + seg] += kick
            p += beat

    # ── نسيم علوي (هواء) ──
    air = rng.normal(0, 1, n).astype(np.float32)
    for _ in range(3):                                    # تنعيم بسيط = هواء
        air = (air + np.roll(air, 1) + np.roll(air, -1)) / 3.0
    air /= (np.abs(air).max() + 1e-9)
    left += air * 0.020
    right += air * 0.026

    stereo = np.stack([left, right], axis=1)
    stereo = _seamless(stereo, xfade=XFADE)[:want]
    # توحيد المستوى: كل الأنماط تطلع بنفس القوة (RMS ثابت) ⇒ المزج مع الأجواء مضبوط
    rms = float(np.sqrt((stereo ** 2).mean())) + 1e-9
    stereo *= (TARGET_RMS / rms)
    peak = float(np.abs(stereo).max()) + 1e-9
    if peak > 0.92:
        stereo *= 0.92 / peak
    return stereo.astype(np.float32)


def write_wav(path, x: np.ndarray, sr: int = SR) -> "object":
    import pathlib
    import wave
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(x, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2 if x.ndim > 1 else 1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def STYLES() -> dict:
    return {
        "music_box": "صندوق موسيقى — ألحان زجاجية ناعمة (حكايات)",
        "lullaby_bell": "تهويدة أجراس — للأطفال والنوم الخفيف",
        "warm_pad": "طبقات دافئة — تركيز وتأمل",
        "lofi_keys": "بيانو بطيء + نبض خفيف (ستادي ريلاكس)",
        "dream_pulse": "نبض حالم هادئ",
        "night_drone": "دْرون ليلي عميق (خلفية طويلة جدًا)",
    }


if __name__ == "__main__":
    import pathlib
    out = pathlib.Path("out/music_test")
    for s in STYLES():
        p = write_wav(out / f"{s}.wav", bed(s, 6.0, seed=abs(hash(s)) % 999))
        print("🎵", s, "→", p, f"{p.stat().st_size/1024:.0f} كيلوبايت")
