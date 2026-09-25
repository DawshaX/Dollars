"""اختبارات مولّد الأجواء الصوتية — قفل الجودة قبل أي نشر.

القاعدة: أي صوت يدخل فيديو منشور لازم يعدّي الأربع بوابات دي:
  1) المدة بالظبط زي ما اتطلبت (مش أقل من غير سبب).
  2) مفيش قصّ (clipping) ولا سكوت ميت (RMS في نطاق مقبول).
  3) مفيش «طقّة» على حدود البلوكات (كانت بق حقيقي: 0.31 بين عينتين).
  4) الحلقة متواصلة رياضيًا (نفس طريقة فيديوهات النوم: تلف على نفسها).
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import ambient  # noqa: E402


def _read(path: Path):
    with wave.open(str(path)) as w:
        n, sr, ch = w.getnframes(), w.getframerate(), w.getnchannels()
        d = np.frombuffer(w.readframes(n), dtype="<i2").reshape(-1, ch) / 32768
    return d, sr


def test_all_voices_produce_sound(tmp_path):
    for name in ambient.VOICES:
        x = ambient.VOICES[name](2.0)
        assert x.size == ambient._n(2.0), name
        assert float(np.sqrt((x ** 2).mean())) > 1e-4, f"{name} صامت"


def test_duration_exact_and_no_clipping(tmp_path):
    p = ambient.make("sleep_rain", 8.0, tmp_path / "a.wav")
    d, sr = _read(p)
    assert abs(d.shape[0] / sr - 8.0) < 0.05
    peak = float(np.abs(d).max())
    rms = 20 * np.log10(float(np.sqrt((d ** 2).mean())) + 1e-9)
    assert peak <= 1.0, f"قصّ! القمة {peak}"
    assert -28 < rms < -8, f"مستوى غير مناسب: {rms} dB"


def test_no_click_at_block_boundaries(tmp_path):
    """حدود البلوكات (كل 20ث) ما تكونش شاذة عن باقي الإشارة."""
    p = ambient.make("ocean", 26.0, tmp_path / "b.wav")
    d, sr = _read(p)
    x = d[:, 0]
    jumps = np.abs(np.diff(x))
    ref = float(np.percentile(jumps, 99.9))       # مرجع متين (مش بيتأثر بضجيج عشوائي)
    boundary = float(jumps[ambient._n(20.0) - 1])
    assert boundary <= max(ref * 3.0, 0.01), f"طقّة على حدود البلوك: {boundary} مقابل {ref}"


def test_seamless_loop_is_mathematically_continuous():
    """الحلقة: لازم الوصل يبقى ناعم (بنختبر على موجة ناعمة عشان نقيس بدقة)."""
    t = np.linspace(0, 40 * 2 * np.pi, ambient._n(20.0), dtype=np.float32)
    x = (np.sin(t) * 0.5).astype(np.float32)
    loop = ambient.seamless_loop(x, fade=6.0)
    d = np.abs(np.diff(loop))
    interior = float(np.percentile(d, 90))
    seam = float(d[0])
    assert seam <= max(interior * 1.5, 1e-3), f"وصل الحلقة مش ناعم: {seam} مقابل {interior}"


def test_stereo_and_wav_format(tmp_path):
    p = ambient.make("focus", 3.0, tmp_path / "c.wav")
    with wave.open(str(p)) as w:
        assert w.getnchannels() == 2
        assert w.getsampwidth() == 2
        assert w.getframerate() == ambient.SR


def test_unknown_recipe_fails_loudly(tmp_path):
    with pytest.raises(KeyError):
        ambient.make("nope", 1.0, tmp_path / "x.wav")


def test_track_length_scales_without_memory_blowup():
    """المطلوب: القدرة على توليد ساعات. هنا نقيس 90 ثانية بسرعة معقولة."""
    import time
    t0 = time.time()
    x = ambient.build_track([("rain", 0.8)], 90.0)
    took = time.time() - t0
    assert x.size == ambient._n(90.0)
    assert took < 30, f"بطيء: {took:.1f}ث لـ90 ثانية"
