"""اختبارات مكتبة المؤثرات (الميمز الصوتية بتاعتنا)."""
import wave

import numpy as np
import pytest

from engine import sfx


def test_all_sfx_render_loud_and_short():
    for name in sfx.SFX:
        x = sfx.render(name)
        peak = float(np.abs(x).max())
        assert 0.5 <= peak <= 1.0, f"{name}: ذروة {peak}"
        assert x.size / sfx.SR > 0.03, f"{name}: قصير جدًا"


def test_no_silence_no_dc():
    for name in sfx.SFX:
        x = sfx.render(name)
        assert float(np.abs(x).mean()) > 1e-4, f"{name}: صامت"
        assert abs(float(x.mean())) < 0.05, f"{name}: فيه إزاحة DC"


def test_build_all_writes_wavs_and_index(tmp_path):
    made = sfx.build_all(tmp_path)
    assert len(made) == len(sfx.SFX)
    assert (tmp_path / "index.json").exists()
    with wave.open(str(made[0]), "rb") as w:
        assert w.getframerate() == sfx.SR and w.getsampwidth() == 2


def test_montage_contains_everything(tmp_path):
    p = sfx.montage(tmp_path / "preview.wav")
    with wave.open(str(p), "rb") as w:
        dur = w.getnframes() / w.getframerate()
    assert dur > 20.0                       # دقيقة تسمع فيها المكتبة كلها


def test_uses_groups_are_valid():
    for kind in sfx.USES:
        names = sfx.by_use(kind)
        assert names and all(n in sfx.SFX for n in names)
    with pytest.raises(KeyError):
        sfx.by_use("nonsense")


def test_comedy_transition_celebration_cover_the_need():
    """كل نوع فيديو لازم يلاقي مؤثراته جاهزة."""
    for video_kind in ("story", "satisfying", "short_comedy"):
        assert sfx.RECOMMENDED[video_kind]
        assert all(n in sfx.SFX for n in sfx.RECOMMENDED[video_kind])
    assert sfx.RECOMMENDED["sleep"] == []      # النوم بلا مؤثرات (هدوء كامل)
