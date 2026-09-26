"""
📖 مُركّب الحِكايات بلا كلام — Dollars Studio
=============================================
بيحوّل «قصة» مكتوبة كبيانات (بيتات) لفيلم كامل: مشاهد حيّة (2D/3D) + شخصيات بتتحرك
+ مؤثرات صوتية + موسيقى/أجواء + انتقالات + كاميرا + طقم جودة سينمائي + بيانات يوتيوب.

المبدأ: **بلا كلام** — مفيش حوار ولا نص على الشاشة؛ القصة تتفهم بالعين.
(العنوان والوصف بيبقوا نص عادي على يوتيوب — ده مش «كلام جوه الفيديو»).

الواجهة:
    story = story.load("nono_rain")            # من content/stories.json
    story.validate()                           # فحص القواعد (بلا كلام · مشاهد معروفة · توقيتات)
    story.render("out/nono_rain.mp4")          # الفيلم كامل (صوت + صورة)
    story.write_package("out/")                # العنوان/الوصف/الوسوم + ملف جاهز للنسخ
"""
from __future__ import annotations

import json
import math
import pathlib
import subprocess
import sys

import numpy as np

from . import ambient, cutout, fx as fx_mod, grade, meta, music as music_mod, proc, sfx, visuals
from . import render3d  # noqa: F401  (تسجيل مشاهد 3D في سجل المحرّك)

ROOT = pathlib.Path(__file__).resolve().parents[1]
STORIES = ROOT / "content" / "stories.json"

TRANSITIONS = ("none", "ink", "glitch", "confetti", "zoom", "fade")


# ───────────────────────────── تشغيل الصوت ─────────────────────────────

def build_audio(beats: list, ambient_name: str | None = None, sr: int = 44100,
                ambient_gain: float = 0.55, music_style: str | None = None,
                music_gain: float = 0.45) -> np.ndarray:
    """خريطة صوتية كاملة: أرضية أجواء هادئة + المؤثرات في توقيتاتها بالظبط."""
    total = sum(float(b.get("dur", 2.0)) for b in beats)
    n = int(total * sr) + sr // 2
    track = np.zeros(n, np.float32)
    if ambient_name:
        try:
            bed = ambient.build_track(
                [("wind", 0.5), ("room_tone", 0.5)] if ambient_name == "calm_night" else
                [("rain", 0.6), ("room_tone", 0.4)] if ambient_name in ("sleep_rain", "rain_only") else
                [("waves", 0.6), ("wind", 0.3)] if ambient_name == "ocean" else
                [("brown_sleep", 0.7), ("wind", 0.2)] if ambient_name == "focus" else
                [("fire", 0.7), ("room_tone", 0.3)] if ambient_name == "fireplace" else
                [("wind", 0.7), ("brown_sleep", 0.4)],
                total + 0.5)
            track[:bed.size] += bed[:n] * ambient_gain
        except Exception:
            pass
    if music_style:                                   # موسيقى من صنعنا تحت الحكاية
        try:
            bed = music_mod.bed(music_style, total + 0.5)
            m = min(bed.shape[0], n)
            track[:m] += (bed[:m, 0] + bed[:m, 1]) * 0.5 * music_gain
        except Exception:
            pass
    t0 = 0.0
    for b in beats:
        dur = float(b.get("dur", 2.0))
        for cue in (b.get("sfx") or []):
            at = max(0.0, float(cue.get("at", 0.0))) + t0
            try:
                clip = sfx.render(cue.get("name", "ding")) * float(cue.get("gain", 1.0))
            except KeyError:
                continue
            j = int(at * sr)
            m = min(clip.size, n - j)
            if m > 0:
                track[j:j + m] += clip[:m]
        t0 += dur
    peak = float(np.max(np.abs(track))) if track.size else 0.0
    if peak > 0.97:
        track *= 0.97 / peak
    return track


def _write_wav(path: pathlib.Path, x: np.ndarray, sr: int = 44100, stereo: bool = True):
    import wave
    import struct
    pcm = np.clip(x, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    if stereo:
        pcm = np.repeat(pcm[:, None], 2, axis=1).reshape(-1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2 if stereo else 1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


# ───────────────────────────── القصة ─────────────────────────────

class Story:
    def __init__(self, data: dict):
        self.d = dict(data)
        self.beats = list(self.d.get("beats") or [])
        self.id = self.d.get("id") or "story"
        self.fps = int(self.d.get("fps", 24))
        self.w, self.h = (self.d.get("size") or [960, 540])[:2]
        self.look = self.d.get("look", "story")
        # بيانات يوتيوب (للعناوين/الوصف/الغلاف)
        self.title = self.d.get("title") or self.id
        self.kw = self.d.get("kw") or f"{self.title} — a wordless story"
        self.thing = self.d.get("thing") or "something new"
        self.hero_name = self.d.get("hero_name") or "our little hero"
        self.video_desc = self.d.get("video_desc") or "a wordless animated story"
        self.ambient = self.d.get("ambient")
        # موسيقى النمط: مضمونة دايمًا (المونتاج أساسي في كل فيديو)
        self.music = self.d.get("music")
        if not self.music:
            import random as _r
            import zlib
            self.music = _r.Random(zlib.crc32(self.id.encode("utf-8")) % 99991).choice(
                ["music_box", "lullaby_bell", "warm_pad"])
        self.title = self.d.get("title") or self.id
        self.characters = self.d.get("characters") or "دولارز"

    # ── فحص ──
    def fx_summary(self) -> list:
        """الإضافات البصرية الفعلية لكل بيت (نفس اللي الرندر بيستخدمه بالظبط)."""
        import random as _r
        import zlib
        base = zlib.crc32(self.id.encode("utf-8")) % 99991
        out = []
        for bi, beat in enumerate(self.beats):
            plan_b = beat.get("fx")
            if plan_b is None:
                plan_b = fx_mod.plan(_r.Random(int(base) + int(bi) * 17), "story", 1)[0]
            out.append([x["kind"] for x in plan_b])
        return out

    def validate(self) -> list:
        problems = []
        if not self.beats:
            problems.append("القصة فاضية (مفيش بيتات)")
        total = 0.0
        for i, b in enumerate(self.beats):
            scene = b.get("scene")
            if scene not in visuals.SCENES:
                problems.append(f"البيت {i+1}: مشهد غير معروف «{scene}»")
            dur = float(b.get("dur", 0))
            if dur <= 0.2:
                problems.append(f"البيت {i+1}: مدة قصيرة جدًا ({dur})")
            total += max(dur, 0.0)
            for c in (b.get("chars") or []):
                if c.get("who") not in cutout.__dict__ and not (cutout.STICKERS / f"{c.get('who')}.png").exists():
                    problems.append(f"البيت {i+1}: شخصية غير موجودة «{c.get('who')}»")
                if c.get("move", "idle") not in cutout.MOVES:
                    problems.append(f"البيت {i+1}: حركة غير معروفة «{c.get('move')}»")
            for cue in (b.get("sfx") or []):
                if cue.get("name") not in sfx.SFX:
                    problems.append(f"البيت {i+1}: مؤثر غير معروف «{cue.get('name')}»")
            if b.get("transition", "none") not in TRANSITIONS:
                problems.append(f"البيت {i+1}: انتقال غير معروف")
            if b.get("caption"):
                problems.append(f"البيت {i+1}: ممنوع نص على الشاشة — إحنا «بلا كلام»")
        if total > 4 * 60 + 1:
            problems.append(f"القصة {total/60:.1f} دقيقة — أطول من 4 دقايق (ده حد القِصص عندنا)")
        if total < 1.0:
            problems.append("القصة أقصر من ثانية")
        return problems

    @property
    def duration(self) -> float:
        return sum(float(b.get("dur", 2.0)) for b in self.beats)

    # ── الرندر ──
    def render(self, out_path, verbose: bool = True, cinema: str | None = None,
               audio_gain: float = 1.0) -> pathlib.Path:
        problems = self.validate()
        if problems:
            raise ValueError("القصة فيها مشاكل:\n- " + "\n- ".join(problems))
        out_path = pathlib.Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        audio = build_audio(self.beats, self.ambient, music_style=self.music) * float(audio_gain)
        wav = out_path.with_suffix(".wav")
        _write_wav(wav, audio)
        silent = out_path.with_name(out_path.stem + "_silent.mp4")
        self._render_video(silent, cinema=cinema, verbose=verbose)
        subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", str(silent), "-i", str(wav), "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-shortest",
                        "-movflags", "+faststart", str(out_path)], check=True)
        silent.unlink(missing_ok=True)
        wav.unlink(missing_ok=True)
        if verbose:
            print(f"🎬 {out_path.name} · {self.duration:.1f} ث · {out_path.stat().st_size/1e6:.1f} ميجا")
        return out_path

    def _render_video(self, path, cinema: str | None = None, verbose: bool = True):
        fps, w, h = self.fps, self.w, self.h
        frames = int(round(self.duration * fps))
        cmd = [proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo",
               "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
               "-g", str(fps * 2), "-movflags", "+faststart", str(path)]
        proc_ = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE)
        beat_at = []
        acc = 0.0
        for b in self.beats:
            beat_at.append(acc)
            acc += float(b.get("dur", 2.0))
        # ملصقات القصة: ثيم القصة (شخصيات + رموز) — لكل بيت ملصق بحركة pop
        import zlib as _z
        from .editor import load_sticker, overlay as _overlay, sticker_pool as _spool
        _sp = _spool("story", _z.crc32(self.id.encode("utf-8")) % 9973)
        st_cache: dict = {}
        st_count = 0

        # مشاهد وكاميرات (تُبنى مرّة لكل بيت)
        cache = {}
        fx_cache: dict = {}
        for i in range(frames):
            t = i / fps
            bi = max(0, min(len(self.beats) - 1, np.searchsorted(beat_at, t, side="right") - 1))
            beat = self.beats[bi]
            local = t - beat_at[bi]
            dur = float(beat.get("dur", 2.0))
            if bi not in cache:
                cache[bi] = visuals.make_scene(beat["scene"], w=w, h=h, fps=fps)
                cache[bi]._first_frame = True
            scene = cache[bi]
            if getattr(scene, "stateful", False) and getattr(scene, "_first_frame", False):
                scene.reset()
                scene._first_frame = False
            bg = scene.raw(local)
            depth = scene.depth(local) if hasattr(scene, "depth") else None
            look = cinema or beat.get("look") or self.look
            if bi not in fx_cache:                     # إضافات بصرية للبيت (تركيب جوه المونتاج)
                plan_b = beat.get("fx")
                if plan_b is None:
                    import random as _r
                    import zlib
                    base = zlib.crc32(self.id.encode("utf-8")) % 99991     # ثابت في كل تشغيل
                    plan_b = fx_mod.plan(_r.Random(int(base) + int(bi) * 17), "story", 1)[0]
                fx_cache[bi] = plan_b
            frame = grade.apply(bg, preset=look, depth=depth,
                                sun_xy=getattr(scene, "sun_xy", (0.7, 0.25)), seed=i,
                                focus=float(beat.get("focus", 0.90)),
                                aperture=float(beat.get("aperture", 0.62)),
                                max_blur=float(beat.get("max_blur", 1.5)))
            # كاميرا 2D (زووم/بان) — قص نافذة وإعادة تكبير
            cam = beat.get("camera") or {}
            zoom = float(cam.get("zoom", 1.0))
            if abs(zoom - 1.0) > 1e-4:
                cw, ch = int(w / zoom), int(h / zoom)
                px = float(cam.get("pan", [0.0, 0.0])[0]) * (w - cw)
                py = float(cam.get("pan", [0.0, 0.0])[1]) * (h - ch)
                cx = int(np.clip((w - cw) * 0.5 + px, 0, max(0, w - cw)))
                cy = int(np.clip((h - ch) * 0.5 + py, 0, max(0, h - ch)))
                frame = np.asarray(proc.upscale(frame[cy:cy + ch, cx:cx + cw], (h, w)), np.float32)
            # الشخصيات
            chars = beat.get("chars") or []
            if chars:
                layer = cutout.Layer(w, h)
                for c in chars:
                    layer.add(cutout.Actor(
                        c["who"], x=float(c.get("x", 0.5)), y=float(c.get("y", 0.72)),
                        scale=float(c.get("scale", 0.32)), move=c.get("move", "idle"),
                        phase=float(c.get("phase", 0.0)) + bi * 1.37, flip=bool(c.get("flip", False)),
                        loop=dur * float(c.get("cycles", 2.0)), tilt=float(c.get("tilt", 0.0)),
                        enter=c.get("enter"), exit=c.get("exit"), blink=bool(c.get("blink", True))))
                frame = layer.compose(frame, local, ambient_color=_ambient_color(frame))
            # إضافات بصرية (ضوء · غبار · لمعات · بلوم) — طبقة تركيب فوق الكادر
            if fx_cache.get(bi):
                frame = fx_mod.apply_all((np.clip(frame, 0, 1) * 255).astype(np.uint8),
                                         fx_cache[bi], local, seed=i) / 255.0
            # ملصقات متحركة (طبقة تركيب حقيقية فوق الكادر)
            if _sp:
                if bi not in st_cache:
                    import random as _rr
                    r2 = _rr.Random(int(_z.crc32(self.id.encode("utf-8")) % 99991) + int(bi) * 31)
                    nm = beat.get("sticker") or r2.choice(_sp)
                    st_cache[bi] = dict(
                        name=nm,
                        at=round(dur * r2.uniform(0.35, 0.55), 2),
                        dur=min(1.7, max(0.8, dur * 0.5)),
                        scale=r2.uniform(0.14, 0.24),
                        pos=r2.choice([(0.74, 0.28), (0.26, 0.70), (0.5, 0.24), (0.76, 0.70), (0.5, 0.80)]),
                        rot=r2.uniform(-0.16, 0.16))
                    st_count += 1
                st = st_cache[bi]
                if st["at"] <= local <= st["at"] + st["dur"]:
                    u = (local - st["at"]) / max(st["dur"], 1e-3)
                    pop = min(1.0, u * 6.0) if u < 0.5 else 1.0
                    spr = st.get("sprite")
                    if spr is None:
                        st["sprite"] = spr = load_sticker(st["name"])
                    frame = _overlay((np.clip(frame, 0, 1) * 255).astype(np.uint8), spr,
                                     st["pos"][0] * w + 9 * math.sin(local * 2.1),
                                     st["pos"][1] * h - h * 0.05 * u,
                                     st["scale"] * (0.6 + 0.4 * pop),
                                     opacity=min(1.0, (1.0 - u) * 2.4),
                                     rot=st["rot"] * math.sin(local * 2.3)) / 255.0
            # انتقال للخروج
            tr = beat.get("transition", "none")
            if tr != "none" and local > dur - 0.45:
                k = (local - (dur - 0.45)) / 0.45
                frame = _blend_transition(frame, tr, k, t, w, h, fps, seed=i)
            proc_.stdin.write(memoryview((np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8)))
        proc_.stdin.close()
        err = proc_.stderr.read().decode("utf-8", "ignore") if proc_.stderr else ""
        if proc_.wait() != 0:
            raise RuntimeError(f"ffmpeg فشل: {err[:400]}")
        self._last_stickers = st_count
        self._last_sticker_names = sorted({v["name"] for v in st_cache.values()})

    # ── بيانات يوتيوب ──
    def metadata(self) -> dict:
        spec = {
            "pillar": "story",
            "kind": "short" if self.duration <= 240 else "long",
            "kw": self.d.get("kw") or self.title,
            "minutes": max(1, round(self.duration / 60)) if self.duration > 90 else None,
            "seconds": int(round(self.duration)) if self.duration <= 90 else None,
            "character": self.d.get("hero_name") or "Nono",
            "thing": self.d.get("thing") or "the little rain cloud",
            "video_desc": self.d.get("video_desc") or
            "hand-animated characters over living 3D backgrounds, generated frame by frame in our studio",
            "pinned_comment": self.d.get("pinned_comment"),
        }
        return meta.build(spec)

    def write_package(self, out_dir) -> dict:
        md = self.metadata()
        files = meta.write_package(md, out_dir)
        files["kdp"] = {}
        return files


def _ambient_color(frame: np.ndarray) -> tuple:
    """لون الجو من الصورة نفسها — عشان الشخصية تندمج مع المشهد."""
    m = frame.mean(axis=(0, 1))
    m = m / max(float(m.max()), 1e-6)
    return tuple(float(0.55 + 0.45 * v) for v in m)


def _blend_transition(frame: np.ndarray, kind: str, k: float, t: float, w: int, h: int,
                      fps: int, seed: int = 0) -> np.ndarray:
    """انتقال بصري جاهز (من ملصقاتنا المتحركة)."""
    scene_names = {"ink": "stinger_ink", "glitch": "stinger_glitch",
                   "confetti": "stinger_confetti", "zoom": "stinger_zoom"}
    k = float(np.clip(k, 0.0, 1.0))
    if kind == "fade":
        return frame * (1.0 - 0.35 * k)
    name = scene_names.get(kind)
    if not name:
        return frame
    if not hasattr(_blend_transition, "_cache"):
        _blend_transition._cache = {}
    key = (name, w, h, fps)
    if key not in _blend_transition._cache:
        _blend_transition._cache[key] = visuals.make_scene(name, w=w, h=h, fps=fps)
    sc = _blend_transition._cache[key]
    ov = np.clip(sc.raw(k * sc.loop_seconds), 0.0, 1.0)
    if kind == "confetti":
        a = np.clip(ov[:, :, :1] * 1.6, 0, 1)
        return np.clip(frame * (1 - a) + ov * a, 0.0, 1.0)
    return np.clip(frame * (1 - 0.55 * k) + ov * (0.55 * k + 0.25 * k), 0.0, 1.0)


# ───────────────────────────── تحميل ─────────────────────────────

def load(story_id: str, path=None) -> Story:
    p = pathlib.Path(path or STORIES)
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "stories" in data:
        for s in data["stories"]:
            if s.get("id") == story_id:
                return Story(s)
        raise KeyError(f"مفيش قصة اسمها {story_id} (المتاح: "
                       f"{', '.join(s['id'] for s in data['stories'])})")
    return Story(data)


def all_stories(path=None) -> list:
    p = pathlib.Path(path or STORIES)
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("stories", []) if isinstance(data, dict) else [data]


def inventory() -> str:
    rows = ["📖 القِصص المتاحة:"]
    for s in all_stories():
        st = Story(s)
        problems = st.validate()
        rows.append(f"  • {st.id:16s} {st.duration:5.1f} ث · {len(st.beats)} بيت · "
                    f"{'✅ سليمة' if not problems else '❌ ' + problems[0]}")
    return "\n".join(rows)


if __name__ == "__main__":
    print(inventory())
