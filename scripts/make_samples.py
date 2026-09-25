"""🎁 عيّنات العرض: فيديو حقيقي + صوت مولّد مدمج (دليل على المصنع كامل)."""
from __future__ import annotations

import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from engine import ambient, visuals  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parents[1] / "samples" / "showcase"
SECONDS = 6.0
RW, RH = 640, 360          # دقة الحساب (تُرفع إلى 720p في الترميز)
OW, OH = 1280, 720

# المشهد → وصفة الصوت (None = بلا صوت)
PLAN = [
    ("rain_glass", "sleep_rain"),
    ("ocean", "ocean"),
    ("fireplace", "fireplace"),
    ("starfield", "calm_night"),
    ("aurora", "calm_night"),
    ("sand_table", None),
    ("pendulum_wave", None),
    ("harmonograph", None),
    ("stinger_confetti", None),
]


def mux(video: pathlib.Path, wav: pathlib.Path, out: pathlib.Path) -> pathlib.Path:
    subprocess.run([visuals.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(video), "-i", str(wav), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, audio in PLAN:
        sc = visuals.make_scene(name, w=RW, h=RH, fps=30)
        loop = OUT / f"{name}_loop.mp4"
        visuals.encode(sc, SECONDS, loop, out_w=OW, out_h=OH, crf=22)
        final = OUT / f"{name}.mp4"
        if audio:
            wav = OUT / f"{name}.wav"
            ambient.make(audio, SECONDS, wav)
            mux(loop, wav, final)
            wav.unlink(missing_ok=True)
            loop.unlink(missing_ok=True)
        else:
            loop.replace(final)
        print(f"✅ {final.name} · {final.stat().st_size/1e6:.1f} ميجا", flush=True)
    print("🎬 خلصت العيّنات كلها →", OUT, flush=True)


if __name__ == "__main__":
    main()
