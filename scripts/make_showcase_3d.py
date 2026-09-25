"""🎬 عيّنات المشاهد ثلاثية الأبعاد بعد الطقم السينمائي (فيديو + صوت)."""
from __future__ import annotations
import pathlib, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import ambient, visuals, render3d  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parents[1] / "samples" / "showcase"
PLAN = [("valley_lake", "calm_night", 20.0), ("snow_pines", "calm_night", 20.0),
        ("planet_rings", "focus", 20.0), ("dunes_moon", "meditation", 20.0)]
RW, RH, OW, OH, FPS = 480, 270, 960, 540, 24

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, audio, secs in PLAN:
        sc = render3d.make_3d(name, w=RW, h=RH, fps=FPS)
        loop = OUT / f"{name}_loop.mp4"
        visuals.encode(sc, min(secs, sc.loop_seconds), loop, out_w=OW, out_h=OH, crf=21)
        try:
            wav = ambient.make(audio, min(secs, sc.loop_seconds), OUT / f"{name}.wav")
        except KeyError:
            wav = ambient.make("calm_night", min(secs, sc.loop_seconds), OUT / f"{name}.wav")
        final = OUT / f"{name}.mp4"
        subprocess.run([visuals.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(loop), "-i", str(wav), "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final)], check=True)
        loop.unlink(missing_ok=True); wav.unlink(missing_ok=True)
        print(f"✅ {final.name} · {final.stat().st_size/1e6:.1f} ميجا", flush=True)

if __name__ == "__main__":
    main()
