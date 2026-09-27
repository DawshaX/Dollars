"""🎬 إضافات المونتاج لازم تظهر في المسارين (مقاطع + صور) — مش في الكود بس."""
import sys
import pathlib

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import overlays, photo, proc  # noqa: E402


def _imgs(tmp_path, n=2, w=270, h=480):
    from PIL import Image
    out = []
    rng = np.random.default_rng(3)
    for i in range(n):
        a = (rng.random((h, w, 3)) * 90 + np.array([40, 70, 110])).astype(np.uint8)
        p = tmp_path / f"src_{i}.jpg"
        Image.fromarray(a).save(p, quality=90)
        out.append(p)
    return out


def _frames(path, w=270, h=480, fps=6):
    import subprocess
    raw = subprocess.run([proc.FFMPEG, "-v", "error", "-i", str(path), "-vf", f"fps={fps},scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3).astype(np.float32)


def test_photo_path_gets_all_overlays(tmp_path):
    out = tmp_path / "ov.mp4"
    photo.render_reel(_imgs(tmp_path), out, seconds=5.0, w=270, h=480, fps=15, look="cinema_cool", seed=5,
                      texts=[{"at": 0.6, "dur": 2.0, "text": "Caption card", "card": True, "y": 0.72}],
                      stickers=[{"code": "1f60d", "at": 0.8, "dur": 1.6, "x": 0.75, "y": 0.3, "size": 0.16}],
                      progress=True, watermark="@xDaw_NoVa", hook="Hook badge")
    assert out.exists() and out.stat().st_size > 5_000
    fr = _frames(out)
    assert len(fr) >= 24
    band = fr[:, 20:70, 30:240]
    pink = ((band[:, :, :, 0] > 190) & (band[:, :, :, 1] < 130) & (band[:, :, :, 2] < 140)).mean(axis=(1, 2))
    assert max(pink[:3]) > 0.12, f"شارة الهوك مش ظاهرة (أقصى نسبة {max(pink[:3]):.3f})"
    assert pink[-1] < 0.05, "شارة الهوك فضلت بعد ٣ ثواني"
    bot = fr[:, 455:472, :]
    assert float(np.abs(np.diff(bot.mean(axis=(1, 2)))).mean()) > 0.1, "شريط التقدّم مش بيتحرك"
    assert float(fr[:, 448:470, 150:265].std()) > 6, "الوترمارك مش ظاهر"
    assert float(np.abs(np.diff(fr[:, 300:400, :].mean(axis=(1, 2)))).max()) > 0.5, "كارت الكابشن مش ظاهر"


def test_overlay_credit_is_present():
    """شرط رخصة Twemoji: الكريديت لازم يتحط في الوصف."""
    assert "Twemoji" in overlays.EMOJI_CREDIT and "CC-BY" in overlays.EMOJI_CREDIT
