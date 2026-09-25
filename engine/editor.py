"""
🎞️ محرّك المونتاج — Dollars Studio
==================================
ده اللي بيحوّل «مشهد» لحاجة **جاهزة للنشر**: قصّ إيقاعي · مؤثرات في التوقيت الصح ·
ملصقات متحركة · حركة كاميرا (زووم/بان/شيك) · صوت ممزوج · **غلاف** · وبيانات يوتيوب كاملة.

الأنواع اللي بيعملها:
    satisfying_short  شورتس مريحة للعين (15-60 ث) — مقاطع + قصّات + مؤثرات
    sleep_long        فيديوهات نوم 3/8/10 ساعات (مشهد حيّ + أجواء) بلا إعادة ترميز
    story_short       مقطع من قصة بلا كلام (يعمل مخرج للقصة الكاملة)
    ambience_short    مقطع 45-60 ث من مشهد نوم للشورتس (يعمل مخرج للطويل)

الواجهة:
    ed = editor.Editor()
    ed.make("satisfying_short", seconds=30, out="out/short.mp4")
    ed.make("sleep_long", hours=10, scene="valley_lake", audio="calm_night", out="out/long.mp4")
"""
from __future__ import annotations

import json
import math
import pathlib
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from engine import ambient, fx, grade, meta, music, proc, sfx, visuals  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
STICKERS = ROOT / "assets" / "stickers"

# مواصفات كل نوع (عرضي 16:9 للطويل · رأسي 9:16 للشورتس)
SPECS = {
    "satisfying_short": dict(w=480, h=854, ow=720, oh=1280, fps=30, look="satisfying", audio=False),
    "story_short":      dict(w=480, h=270, ow=960, ow_h=540, fps=30, look="story", audio=True),
    "ambience_short":   dict(w=480, h=854, ow=720, oh=1280, fps=30, look=None, audio=True),
    "sleep_long":       dict(w=480, h=270, ow=1920, oh=1080, fps=30, look=None, audio=True),
}

MOVES = ("zoom_in", "zoom_out", "pan_left", "pan_right", "drift_up", "shake", "still")


# ───────────────────────────── أدوات ─────────────────────────────

def _font(size: int):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        if pathlib.Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def load_sticker(name: str) -> Image.Image | None:
    p = STICKERS / f"{name}.png"
    if not p.exists():
        return None
    return Image.open(p).convert("RGBA")


def camera(frame: np.ndarray, move: str, k: float, seed: int = 0) -> np.ndarray:
    """حركة كاميرا بالقصّ والتكبير — بتحسّ إن المشهد مصوّر بكاميرا حقيقية."""
    h, w = frame.shape[:2]
    if move == "still":
        return frame
    z = 1.0
    dx = dy = 0.0
    if move == "zoom_in":
        z = 1.0 + 0.16 * k
    elif move == "zoom_out":
        z = 1.16 - 0.16 * k
    elif move in ("pan_left", "pan_right"):
        z = 1.12
        dx = (0.06 if move == "pan_right" else -0.06) * (k - 0.5)
    elif move == "drift_up":
        z = 1.10
        dy = -0.05 * (k - 0.5)
    elif move == "shake":
        z = 1.06
        a = (1.0 - k) ** 2
        dx = 0.012 * a * math.sin(k * 60 + seed)
        dy = 0.010 * a * math.sin(k * 47 + seed * 1.7)
    cw, ch = int(w / z), int(h / z)
    x0 = int(np.clip((w - cw) / 2 + dx * w, 0, w - cw))
    y0 = int(np.clip((h - ch) / 2 + dy * h, 0, h - ch))
    crop = frame[y0:y0 + ch, x0:x0 + cw]
    img = Image.fromarray(crop).resize((w, h), Image.BILINEAR)
    return np.asarray(img, dtype=np.uint8)


def overlay(frame_u8: np.ndarray, sprite: Image.Image, cx: float, cy: float, scale: float,
            opacity: float = 1.0, rot: float = 0.0) -> np.ndarray:
    """يضع ملصق متحرك فوق الكادر (مع شفافية ودوران)."""
    if sprite is None or opacity <= 0.01:
        return frame_u8
    base = Image.fromarray(frame_u8).convert("RGBA")
    sw = max(8, int(base.width * scale))
    sh = max(8, int(sprite.height * sw / max(1, sprite.width)))
    sp = sprite.resize((sw, sh), Image.LANCZOS)
    if abs(rot) > 0.5:
        sp = sp.rotate(rot, expand=True, resample=Image.BICUBIC)
    if opacity < 0.999:
        a = sp.split()[3].point(lambda v: int(v * opacity))
        sp.putalpha(a)
    base.alpha_composite(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)))
    return np.asarray(base.convert("RGB"), dtype=np.uint8)


# ───────────────────────────── بناء المونتاج ─────────────────────────────

def plan_shots(pillar: str, seconds: float, seed: int = 7,
               moves: list | None = None, scenes: list | None = None) -> list:
    """
    خطة القصّ: مقاطع بأطوال مختلفة (3-9 ث) + حركة + مؤثرات + ملصقات.
    القاعدة: أول ثانية لازم تخطف العين (حركة قوية + مؤثر).
    """
    rng = random.Random(seed)
    if scenes:                                  # مرجع بصري (Pinterest/Openverse) حدّد المشاهد
        try:
            from engine import render3d  # noqa: F401  (بيسجّل مشاهد 3D)
        except Exception:
            pass
        pool = [s for s in scenes if s in visuals.SCENES]
        scenes = pool or None
    if not scenes:
        scenes = [s for s in visuals.SMILE_SCENES if not s.startswith("stinger")]
        if pillar == "ambience":
            scenes = list(visuals.SLEEP_SCENES)
    opens = [m for m in (moves or []) if m in MOVES] or ["zoom_in", "pan_left", "pan_right", "drift_up", "shake"]
    rest = [m for m in (moves or []) if m in MOVES] or list(MOVES)
    shots, t = [], 0.0
    first = True
    while t < seconds - 0.5:
        dur = min(rng.choice([3.0, 4.0, 5.0, 6.0, 7.5]), max(1.5, seconds - t))
        pool = [x for x in scenes if not shots or x != shots[-1]["scene"]] or list(scenes)
        scene = rng.choice(pool)               # ما نكررش نفس المشهد ورا بعضه
        move = rng.choice(opens if first else rest)
        cues = []
        if first:
            cues.append(dict(name=rng.choice(["whoosh", "swipe", "riser"]), at=0.0, gain=0.9))
        if rng.random() < 0.55:
            cues.append(dict(name=rng.choice(sfx.RECOMMENDED["satisfying"]), at=round(dur * 0.55, 2),
                             gain=0.7))
        if rng.random() < 0.35 and not first:
            cues.append(dict(name=rng.choice(["impact", "bass_drop", "pop"]), at=0.0, gain=0.55))
        stickers = []
        if rng.random() < 0.30:
            stickers.append(dict(name=rng.choice(sfx.__dict__ and ["sparkle", "star", "burst", "heart",
                                                                  "check"]),
                                 at=round(dur * 0.35, 2), dur=min(1.6, dur * 0.5),
                                 scale=rng.uniform(0.16, 0.30),
                                 pos=rng.choice([(0.72, 0.30), (0.28, 0.72), (0.5, 0.78), (0.75, 0.68)])))
        shots.append(dict(scene=scene, dur=dur, move=move, cues=cues, stickers=stickers,
                          look=rng.choice(["satisfying", "dream"])))
        t += dur
        first = False
    pillar_key = "ambience" if pillar == "ambience" else "satisfying"
    plans = fx.plan(random.Random(seed + 77), pillar_key, len(shots))     # إضافات بصرية لكل مقطع
    for sh, pl in zip(shots, plans):
        sh["fx"] = pl
    return shots


def mix_audio(seconds: float, shots: list, ambient_name: str | None = None,
              sr: int = 44100, music_style: str | None = None,
              music_gain: float = 0.55) -> np.ndarray:
    """يمزج الأجواء + الموسيقى (بتاعتنا) + المؤثرات في مسار ستيريو واحد في التوقيت الصح."""
    n = int(seconds * sr)
    left = np.zeros(n, np.float32)
    right = np.zeros(n, np.float32)
    if ambient_name:
        try:
            tmp = ROOT / "out" / "_amb.wav"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            ambient.make(ambient_name, max(3.0, seconds), tmp)
            import wave
            with wave.open(str(tmp), "rb") as w:
                raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
                if w.getnchannels() == 2:
                    raw = raw.reshape(-1, 2)
                    left = raw[:n, 0] * 0.9 if raw.shape[0] >= n else np.pad(raw[:, 0], (0, n - raw.shape[0])) * 0.9
                    right = raw[:n, 1] * 0.9 if raw.shape[0] >= n else np.pad(raw[:, 1], (0, n - raw.shape[0])) * 0.9
                else:
                    left = right = raw[:n] * 0.9
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    at = 0.0
    for sh in shots:
        for cue in sh["cues"]:
            j = int((at + float(cue.get("at", 0.0))) * sr)
            if j >= n:
                continue
            x = sfx.render(cue["name"]) * float(cue.get("gain", 0.7))
            m = min(x.size, n - j)
            left[j:j + m] += x[:m]
            right[j:j + m] += x[:m] * 0.98
        at += float(sh["dur"])
    if music_style:                                    # أرضية موسيقية مولّدة بالكود
        try:
            bed = music.bed(music_style, max(3.0, seconds))
            m = min(bed.shape[0], n)
            left[:m] += bed[:m, 0] * music_gain
            right[:m] += bed[:m, 1] * music_gain
        except Exception:
            pass
    peak = max(float(np.abs(left).max()), float(np.abs(right).max()), 1e-6)
    k = min(1.0, 0.92 / peak)
    return np.stack([np.clip(left * k, -1, 1), np.clip(right * k, -1, 1)], axis=1)


def _write_wav(path, stereo: np.ndarray, sr: int = 44100):
    import wave
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def render_shots(shots: list, out_path, w: int, h: int, fps: int, look: str,
                 out_w: int | None = None, out_h: int | None = None, crf: int = 21,
                 progress: bool = False) -> pathlib.Path:
    """يرندر الخطة كاملة بكاميرا + ملصقات + طقم الجودة السينمائي."""
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames_total = int(round(sum(s["dur"] for s in shots) * fps))
    cmd = [proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if out_w and out_h and (out_w, out_h) != (w, h):
        cmd += ["-vf", f"scale={out_w}:{out_h}:flags=lanczos"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-g", str(fps * 2), "-movflags", "+faststart", str(out_path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    sprite_cache: dict = {}
    frames = 0
    start_at = 0.0
    for si, sh in enumerate(shots):
        sc = visuals.make_scene(sh["scene"], w=w, h=h, fps=fps)
        if getattr(sc, "stateful", False):
            sc.reset()
        look_sh = sh.get("look") or look
        durs = float(sh["dur"])
        n_frames = max(1, int(round(durs * fps)))
        for i in range(n_frames):
            k = i / max(1, n_frames - 1)
            t = k * min(durs, sc.loop_seconds)
            base = sc.raw(t)
            depth = sc.depth(t) if hasattr(sc, "depth") else None
            fr = grade.apply(base, preset=look_sh, depth=depth,
                             sun_xy=getattr(sc, "sun_xy", (0.7, 0.25)), seed=si * 100 + i,
                             focus=0.8, aperture=0.5, max_blur=2.2)
            fr = camera((np.clip(fr, 0, 1) * 255).astype(np.uint8), sh["move"], k, seed=si)
            if sh.get("fx"):                       # إضافات بصرية (ضوء · هالة · غبار · لمعات …)
                fr = fx.apply_all(fr, sh["fx"], i / fps, seed=si * 31 + i)
            # ملصقات متحركة: بتظهر بحركة «pop» وتطير لفوق بنعومة
            for st in sh.get("stickers", []):
                at, dur = float(st.get("at", 0.0)), float(st.get("dur", 1.2))
                lt = i / fps
                if not (at <= lt <= at + dur):
                    continue
                u = (lt - at) / max(dur, 1e-3)
                pop = min(1.0, u * 6.0) if u < 0.5 else 1.0
                if st["name"] not in sprite_cache:
                    sprite_cache[st["name"]] = load_sticker(st["name"])
                px, py = st.get("pos", (0.7, 0.65))
                fr = overlay(fr, sprite_cache[st["name"]],
                             px * w + 10 * math.sin(lt * 2.2),
                             py * h - h * 0.05 * u, float(st.get("scale", 0.22)) * (0.6 + 0.4 * pop),
                             opacity=min(1.0, (1.0 - u) * 2.2))
            p.stdin.write(memoryview(np.ascontiguousarray(fr)))
            frames += 1
            if progress and frames % 240 == 0:
                print(f"   … {frames}/{frames_total} كادر", flush=True)
        start_at += durs
    p.stdin.close()
    err = p.stderr.read().decode("utf-8", "ignore") if p.stderr else ""
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg فشل: {err[:300]}")
    return out_path



# ───────────────────── مونتاج الطويلة: مقدمة + شاشة نهاية ─────────────────────

def _cc_shift(stamp: str, add: float) -> str:
    """يبدّل توقيت الفصل بعد المقدمة (بلا كسر صيغة يوتيوب)."""
    try:
        parts = [int(x) for x in str(stamp).split(":")]
        secs = 0
        for p in parts:
            secs = secs * 60 + p
        secs += int(add)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    except Exception:
        return stamp


def _concat(parts: list, out_path) -> pathlib.Path:
    """يلزّق الأجزاء **بلا إعادة ترميز** (نفس الترميز ⇒ سريع جدًا)."""
    out_path = pathlib.Path(out_path)
    lst = out_path.with_suffix(".txt")
    lst.write_text("".join(f"file '{pathlib.Path(p).resolve()}'\n" for p in parts), encoding="utf-8")
    cmd = [proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
           "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out_path)]
    r = subprocess.run(cmd, capture_output=True)
    lst.unlink(missing_ok=True)
    if r.returncode != 0:                      # خطة بديلة: ترميز خفيف لو التركيب المباشر رفض
        lst.write_text("".join(f"file '{pathlib.Path(p).resolve()}'\n" for p in parts), encoding="utf-8")
        cmd = [proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
               "-i", str(lst), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-maxrate", "1200k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
               str(out_path)]
        subprocess.run(cmd, check=True, capture_output=True)
        lst.unlink(missing_ok=True)
    return out_path


def long_format(hours: float) -> dict:
    """
    مقاس وبتريت الطويلة حسب طولها — عشان 10 ساعات ما يبقوش جيجابايتات تتخنق بيها السيرفر:
    ≤3 ساعات: 1080p · 1.2 ميجا/ث · 6+ ساعات: 720p ببتريت أقل (نفس الجودة تقريبًا للمشاهد الهادية).
    """
    hours = max(0.1, float(hours))
    cap_mb = 2600.0                                  # سقف الحجم لكل فيديو طويل
    mbps = min(1.2, (cap_mb * 8.0) / (hours * 3600.0))
    if hours >= 6:
        w, h = 1280, 720
    else:
        w, h = 1920, 1080
    return dict(w=w, h=h, maxrate=f"{int(mbps * 1000)}k", cap_mb=cap_mb)


def long_intro(out_dir, seconds: float = 12.0, seed: int = 5, moves=None, scenes=None,
               look: str = "cinema_cool", out_w: int = 1920, out_h: int = 1080) -> pathlib.Path:
    """مقدمة مونتاج للطويلة: 3 مقاطع سريعة + كاميرا + إضافات + مؤثرات + موسيقى."""
    shots = plan_shots("ambience", seconds, seed=seed, moves=moves, scenes=scenes)
    silent = pathlib.Path(out_dir) / "_intro_silent.mp4"
    render_shots(shots, silent, 480, 270, 30, look, out_w=out_w, out_h=out_h, crf=23)
    audio = mix_audio(sum(s["dur"] for s in shots), shots, ambient_name="calm_night",
                      music_style="warm_pad", music_gain=0.5)
    wav = pathlib.Path(out_dir) / "_intro.wav"
    _write_wav(wav, audio)
    out = pathlib.Path(out_dir) / "_intro.mp4"
    total = sum(s["dur"] for s in shots)
    subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(silent),
                    "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                    "-ac", "2", "-af", "apad", "-t", f"{total:.3f}", "-movflags", "+faststart",
                    str(out)], check=True)
    silent.unlink(missing_ok=True); wav.unlink(missing_ok=True)
    return out


def long_outro(out_dir, seconds: float = 10.0, seed: int = 9,
               out_w: int = 1920, out_h: int = 1080) -> pathlib.Path:
    """شاشة نهاية القناة: كارتنا بهوية القناة + موسيقى بتاعتنا (بحركة ناعمة)."""
    card = ROOT / "assets" / "brand" / "endcard_1280x720.png"
    music_wav = pathlib.Path(out_dir) / "_outro.wav"
    try:
        bed = music.bed("warm_pad", seconds, seed=seed)
        _write_wav(music_wav, bed * 0.8)
    except Exception:
        music_wav = None
    out = pathlib.Path(out_dir) / "_outro.mp4"
    cmd = [proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    if card.exists():
        cmd += ["-loop", "1", "-i", str(card)]
        vf = (f"scale={out_w}:{out_h}:flags=lanczos,"
              "zoompan=z='min(zoom+0.00035,1.06)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
              f"s={out_w}x{out_h},"
              "fade=t=in:st=0:d=0.9,fade=t=out:st=%.1f:d=0.9" % max(0.0, seconds - 1.0))
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=0x0a0e1e:s={out_w}x{out_h}:r=30"]
        vf = "fade=t=in:st=0:d=0.9"
    if music_wav:
        cmd += ["-i", str(music_wav)]
    cmd += ["-vf", vf, "-r", "30", "-t", str(seconds)]
    if music_wav:
        # apad: نضمن إن الصوت مايقصّرش الفيديو (كان بيقطع الفيديو قبل نهاية الفيد عن غلطة)
        cmd += ["-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2", "-af", "apad",
                "-t", str(seconds)]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "1200k",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    music_wav and music_wav.unlink(missing_ok=True)
    return out


# ───────────────────────────── الأغلفة ─────────────────────────────

def thumbnail(scene: str, texts: list, out_path, look: str | None = None,
              sticker: str | None = None, at: float = 6.0, size=(1280, 720)) -> pathlib.Path:
    """غلاف جاهز: كادر من المشهد + طقم الجودة + ملصق + نص كبير."""
    w, h = 480, 270
    sc = visuals.make_scene(scene, w=w, h=h, fps=30)
    frame = sc.raw(at)
    depth = sc.depth(at) if hasattr(sc, "depth") else None
    fr = grade.apply(frame, preset=look or visuals.LOOKS.get(scene, "cinema_night"), depth=depth,
                     sun_xy=getattr(sc, "sun_xy", (0.7, 0.25)), focus=0.75, aperture=0.4, max_blur=2.0)
    img = Image.fromarray((np.clip(fr, 0, 1) * 255).astype(np.uint8)).resize(size, Image.LANCZOS).convert("RGBA")
    if sticker:
        sp = load_sticker(sticker)
        if sp is not None:
            sw = int(size[0] * 0.26)
            sp = sp.resize((sw, int(sp.height * sw / sp.width)), Image.LANCZOS)
            img.alpha_composite(sp, (int(size[0] * 0.66), int(size[1] * 0.44)))
    d = ImageDraw.Draw(img)
    # شريط خفيف + نص كبير واضح (النص في الأغلفة مسموح — هو عنوان الفيديو)
    y = int(size[1] * 0.62)
    for i, line in enumerate(texts[:2]):
        f = _font(int(size[1] * (0.13 if i == 0 else 0.095)))
        txt = line.upper()
        box = d.textbbox((0, 0), txt, font=f)
        tw, th = box[2] - box[0], box[3] - box[1]
        x = (size[0] - tw) // 2
        pad = int(th * 0.35)
        d.rounded_rectangle([x - pad, y - pad, x + tw + pad, y + th + pad * 1.6],
                            radius=int(th * 0.35), fill=(0, 0, 0, 165))
        d.text((x + 3, y + 3), txt, font=f, fill=(0, 0, 0, 200))
        d.text((x, y), txt, font=f, fill=(255, 255, 255, 255))
        y += th + pad * 3
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path, quality=92)
    return out_path


# ───────────────────────────── الواجهة ─────────────────────────────

class Editor:
    """المخرج: بياخد طلب → يطلّع فيديو + صوت + غلاف + بيانات جاهزة للنشر."""

    def __init__(self, out_dir="out", seed: int = 7):
        self.out = pathlib.Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        self.log: list = []

    def make(self, kind: str, out_name: str | None = None, **kw) -> dict:
        if kind == "satisfying_short":
            return self._short(kind, out_name, pillar="satisfying", **kw)
        if kind == "ambience_short":
            return self._short(kind, out_name, pillar="ambience", **kw)
        if kind == "sleep_long":
            return self._long(out_name, **kw)
        if kind == "story_short":
            return self._story_short(out_name, **kw)
        raise KeyError(f"نوع غير معروف: {kind}")

    # ── شورتس ──
    def _short(self, kind: str, out_name: str | None, pillar: str = "satisfying",
               seconds: float = 30.0, seed: int | None = None, **kw) -> dict:
        seed = self.seed if seed is None else seed
        sp = dict(SPECS[kind])
        shots = plan_shots(pillar, seconds, seed=seed, moves=kw.get("moves"), scenes=kw.get("scenes"))
        name = out_name or f"{kind}_{seed}_{int(seconds)}s"
        silent = self.out / f"{name}_silent.mp4"
        video = self.out / f"{name}.mp4"
        look = kw.get("look") or sp.get("look") or ("cinema_cool" if pillar == "ambience" else "satisfying")
        render_shots(shots, silent, sp["w"], sp["h"], sp["fps"], look,
                     out_w=sp["ow"], out_h=sp["oh"], crf=21)
        ambient_name = kw.get("audio") if pillar == "ambience" else None
        if pillar == "ambience" and not ambient_name:
            ambient_name = random.Random(seed).choice(["sleep_rain", "calm_night", "ocean", "fireplace"])
        style = kw.get("music")
        if style is None:                                  # اختيار تلقائي حسب النوع
            style = (random.Random(seed + 11).choice(["warm_pad", "dream_pulse", "night_drone"])
                     if pillar == "ambience" else
                     random.Random(seed + 11).choice(["music_box", "lofi_keys", "dream_pulse", "warm_pad"]))
        audio = mix_audio(seconds, shots, ambient_name=ambient_name, music_style=style,
                          music_gain=0.5 if pillar == "ambience" else 0.62)
        wav = self.out / f"{name}.wav"
        _write_wav(wav, audio)
        subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(video)], check=True)
        silent.unlink(missing_ok=True)
        wav.unlink(missing_ok=True)
        # بيانات + غلاف
        scene0 = shots[0]["scene"]
        spec = dict(pillar=pillar if pillar != "ambience" else "sleep", seconds=int(seconds),
                    kind="short", scene=scene0, duration_bucket=f"{int(seconds)}s")
        md = meta.build(spec)
        md["shot_list"] = [{"scene": s["scene"], "dur": s["dur"], "move": s["move"],
                            "sfx": [c["name"] for c in s["cues"]],
                            "fx": [x["kind"] for x in s.get("fx", [])],
                            "stickers": [x["name"] for x in s.get("stickers", [])]} for s in shots]
        md["montage"] = {"shots": len(shots), "music": style, "look": look,
                         "camera_moves": sorted({s["move"] for s in shots}),
                         "fx_layers": sum(len(s.get("fx", [])) for s in shots),
                         "sfx_cues": sum(len(s["cues"]) for s in shots)}
        thumb = thumbnail(scene0, md["thumbnail_texts"][:2], self.out / f"{name}_thumb.jpg",
                          look=look, sticker=random.Random(seed).choice(["star", "sparkle", "burst"]))
        files = meta.write_package(md, self.out)
        record = dict(kind=kind, video=str(video), thumbnail=str(thumb), meta=md,
                      meta_files=files, seconds=seconds, scene=scene0, shots=len(shots))
        self.log.append(record)
        return record

    # ── قصص ──
    def _story_short(self, out_name: str | None, story_id: str | None = None,
                     seconds: float = 40.0, **kw) -> dict:
        """قصة بلا كلام: المخرج بيسلّم الفيديو الكامل بالموسيقى والإضافات والتحريك."""
        from engine import story as story_engine
        stories = [x if isinstance(x, story_engine.Story) else story_engine.Story(x)
                   for x in story_engine.all_stories()]
        if not stories:
            raise RuntimeError("مفيش قصص — زوّد content/stories.json")
        if story_id:
            st = next((x for x in stories if x.id == story_id), None)
            if st is None:
                raise KeyError(f"قصة غير معروفة: {story_id} — المتاح: {[x.id for x in stories]}")
        else:
            st = random.Random(self.seed).choice(stories)
        if kw.get("music") and not getattr(st, "music", None):
            st.music = kw["music"]                 # موسيقى الوصفة لما القصة مالهاش تعريف
        full = pathlib.Path(out_name) if out_name else self.out / f"{st.id}_full.mp4"
        full.parent.mkdir(parents=True, exist_ok=True)
        st.render(full, verbose=False, cinema=kw.get("look") or None)
        # بيانات يوتيوب كاملة (عنوان · وصف · وسوم · إفصاح AI) + المونتاج
        md = meta.build(dict(pillar="story", kind="short", kw=getattr(st, "kw", None),
                             seconds=round(st.duration), scene=(st.beats[0] or {}).get("scene"),
                             character=getattr(st, "hero_name", None),
                             thing=getattr(st, "thing", None),
                             duration_bucket=f"{int(round(st.duration))}s"))
        md["title"] = getattr(st, "title", st.id)
        md["video_desc"] = getattr(st, "video_desc", None)
        md["story_id"] = st.id
        md["montage"] = {"beats": len(getattr(st, "beats", [])), "assembled": True,
                         "music": getattr(st, "music", None), "ambient": getattr(st, "ambient", None),
                         "look": kw.get("look"),
                         "fx_layers": sum(len(v) for v in st.fx_summary()),
                         "fx_by_beat": st.fx_summary(),
                         "scenes": sorted({b.get("scene") for b in getattr(st, "beats", []) if b.get("scene")})}
        first_scene = (st.beats[0] or {}).get("scene") or "starfield"
        try:
            thumb = thumbnail(first_scene, (md.get("thumbnail_texts") or ["WORDLESS STORY"])[:2],
                              self.out / f"{st.id}_thumb.jpg", look=getattr(st, "look", None),
                              sticker="star")
        except Exception:
            thumb = None
        files = meta.write_package(md, self.out)
        record = dict(kind="story_short", video=str(full), story=st.id, meta=md,
                      meta_files=files, thumbnail=str(thumb) if thumb else None,
                      seconds=st.duration, montage=md["montage"])
        self.log.append(record)
        return record

    # ── الطويلة (نوم) ──
    def _long(self, out_name: str | None, hours: float = 10.0, scene: str = "valley_lake",
              audio: str = "calm_night", look: str | None = None, loop_seconds: float = 40.0,
              moves: list | None = None, **kw) -> dict:
        look = visuals.LOOKS.get(scene) or look or "cinema_cool"
        # دقّة الرندر: المشاهد 2D بتتطلع 960×540 (وبعدين 1080p) · المشاهد 3D غالية فبتفضل 480×270
        try:
            from engine import render3d  # noqa: F401  (تسجيل مشاهد 3D)
        except Exception:
            pass
        is3d = bool(getattr(visuals.SCENES.get(scene), "is_3d", False))
        rw, rh = (480, 270) if is3d else (960, 540)
        loop = self.out / f"{scene}_loop.mp4"
        fmt = long_format(hours)
        sc = visuals.make_scene(scene, w=rw, h=rh, fps=30)
        visuals.encode(sc, min(loop_seconds, sc.loop_seconds), loop, out_w=fmt["w"], out_h=fmt["h"],
                       crf=23, maxrate=fmt["maxrate"], cinema=look)   # سقف حجم: الطويلة تفضل قابلة للرفع
        wav = ambient.make(audio, min(loop_seconds, sc.loop_seconds), self.out / f"{audio}.wav")
        name = out_name or f"{scene}_{int(hours)}h"
        video = self.out / f"{name}.mp4"
        body = self.out / f"{name}_body.mp4"
        visuals.long_video(loop, body, hours * 3600, audio_wav=wav)
        loop.unlink(missing_ok=True)
        wav.unlink(missing_ok=True)
        intro_dur = 0.0
        outro_dur = 0.0
        assembled = False
        md_parts: dict = {}
        try:                                      # المونتاج أساسي: مقدمة + شاشة نهاية
            intro = long_intro(self.out, seed=self.seed + 3, moves=moves,
                              out_w=fmt["w"], out_h=fmt["h"])
            outro = long_outro(self.out, seed=self.seed + 9, out_w=fmt["w"], out_h=fmt["h"])
            intro_dur = round(proc.duration(intro) or 12.0, 2)
            outro_dur = round(proc.duration(outro) or 10.0, 2)
            assembled = True
            _concat([intro, body, outro], video)
            joined = proc.duration(video)
            parts_sum = round(intro_dur + (proc.duration(body) or 0.0) + outro_dur, 2)
            if joined and abs(joined - parts_sum) > 1.0:
                print(f"⚠️ فرق في التلزيق: {joined:.2f} ث مقابل {parts_sum:.2f} ث", flush=True)
            md_parts = dict(intro_seconds=intro_dur, outro_seconds=outro_dur,
                            assembled_seconds=round(joined, 2) if joined else None)
            for p in (intro, body, outro):
                p.unlink(missing_ok=True)
        except Exception as e:                    # لو حصل أي عارض: الفيديو الأساسي يكفي
            print(f"⚠️ مونتاج الطويلة اتعذّر ({type(e).__name__}) — الفيديو الأساسي اتنشر", flush=True)
            body.replace(video)
        md = meta.build(dict(pillar="sleep" if scene in visuals.SLEEP_SCENES else "focus",
                             hours=int(hours), kind="long", scene=scene,
                             kw={"valley_lake": "Night Lake Ambience", "snow_pines": "Snow Forest Sounds",
                                 "dunes_moon": "Desert Night Winds", "planet_rings": "Deep Space Ambience",
                                 "rain_glass": "Rain on Window", "ocean": "Ocean Waves",
                                 "fireplace": "Fireplace Crackling", "starfield": "Deep Space Sleep",
                                 "aurora": "Aurora Night Sky", "black_screen": "Black Screen Sleep"
                                 }.get(scene, "Sleep Sounds")))
        if intro_dur and md.get("chapters"):       # الفصول تتزحّ للوقت الحقيقي بعد المقدمة
            md["chapters"] = ["0:00 ابتداء"] + [f"{_cc_shift(c.split(' ', 1)[0], intro_dur)} {c.split(' ', 1)[1]}"
                                               if " " in c else c for c in md["chapters"]]
        md["montage"] = {"assembled": assembled, "out_size": [fmt["w"], fmt["h"]],
                         "maxrate": fmt["maxrate"], "size_cap_mb": fmt["cap_mb"], **md_parts,
                         "look": look, "music": "warm_pad", "body_loop_seconds": loop_seconds,
                         "body_reencoded": False, "scene": scene, "audio": audio,
                         "camera_moves": MOVES if not moves else list(moves)}
        thumb = thumbnail(scene, md["thumbnail_texts"][:2], self.out / f"{name}_thumb.jpg", look=look)
        files = meta.write_package(md, self.out)
        record = dict(kind="sleep_long", video=str(video), thumbnail=str(thumb), meta=md,
                      meta_files=files, hours=hours, scene=scene, audio=audio)
        self.log.append(record)
        return record


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="محرّك المونتاج")
    ap.add_argument("kind", choices=["satisfying_short", "ambience_short", "sleep_long", "story_short"])
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--hours", type=float, default=10.0)
    ap.add_argument("--scene", default="valley_lake")
    ap.add_argument("--audio", default="calm_night")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="out/preview")
    a = ap.parse_args()
    ed = Editor(a.out, seed=a.seed)
    if a.kind == "sleep_long":
        rec = ed.make(a.kind, hours=a.hours, scene=a.scene, audio=a.audio)
    else:
        rec = ed.make(a.kind, seconds=a.seconds)
    print(json.dumps({k: v for k, v in rec.items() if k != "meta"}, ensure_ascii=False, indent=1, default=str))
