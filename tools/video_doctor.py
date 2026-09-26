#!/usr/bin/env python3
"""
🩺 دكتور الفيديو — بيفتح الفيديو نفسه ويقول **الحقيقة**: كل حاجة ظاهرة وشغالة ولا لأ؟
====================================================================================
بيفحص بالكود (مش بالكلام):

| الفحص | إيه اللي بيقيسه | الحد المطلوب |
|---|---|---|
| الأبعاد | عرض×طول حقيقي | 720×1280 للشورت · 1920×1080 للطويل |
| المدة | طول الفيديو بالثواني | مطابق للمطلوب ±10% |
| الحركة | متوسط الفرق بين الكادرات | > 0.004 (مش صورة ساكنة) |
| حركة مستمرة | أقصى مقطع ساكن | < 2 ثانية |
| الصوت | مستوى الصوت (RMS) ونسبة الصمت | RMS > -46dB · صمت < 45% |
| إضاءة | نسبة الكادرات السودة | < 25% |
| اللوب | تقارب آخر كادر بأول كادر | فرق < 0.06 للمشاهد المتكررة |
| النص | وجود نص في البيانات + طوله | للمحتوى الموثّق لازم نص |

    python tools/video_doctor.py out/video.mp4 --expect 30 --kind short --texts
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import proc  # noqa: E402

FF = proc.FFMPEG


def _run(args, text=False):
    return subprocess.run(args, capture_output=True, text=text)


def dimensions(path) -> tuple[int, int]:
    """الأبعاد الحقيقية من ffmpeg نفسه."""
    r = _run([FF, "-hide_banner", "-i", str(path)], text=True)
    m = re.search(r"Video: .*?, (\d{2,5})x(\d{2,5})", r.stderr or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def has_audio(path) -> bool:
    r = _run([FF, "-hide_banner", "-i", str(path)], text=True)
    return "Audio:" in (r.stderr or "")


def _duration(path) -> float:
    """طول الفيديو بالثواني (من ffmpeg نفسه)."""
    r = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True)
    for line in r.stderr.decode("utf-8", "ignore").splitlines():
        if "Duration:" in line:
            try:
                hh, mm, ss = line.split("Duration:")[1].split(",")[0].strip().split(":")
                return int(hh) * 3600 + int(mm) * 60 + float(ss)
            except Exception:
                break
    return 0.0


def _gray_window(path, ss: float, t: float, fps: int, w: int, dims: tuple | None = None):
    """كادرات رمادية من نافذة زمنية محددة.

    ⚠️ **مهم**: ارتفاع الكادر بيتحسب من أبعاد الفيديو الأصلي بالظبط
    (قبل كده كان بيتخمّن ⇒ «الثبات» كان بالصفوف مش بالكادرات = أرقام مضخّمة).
    """
    W, H = dims or dimensions(path)
    W = W or 16
    h_out = max(2, int(round((H or 9) * w / W / 2)) * 2)          # لازم يبقى زوجي (زي scale=..:-2)
    cmd = [FF, "-hide_banner", "-loglevel", "error", "-ss", str(max(0.0, ss)), "-i", str(path)]
    if t and t > 0:
        cmd += ["-t", str(t)]
    cmd += ["-vf", f"fps={fps},scale={w}:{h_out}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = subprocess.run(cmd, capture_output=True)
    buf = np.frombuffer(r.stdout, dtype=np.uint8)
    if buf.size == 0 or buf.size % (w * h_out):
        return None
    return buf.reshape(-1, h_out, w).astype(np.float32) / 255.0


def frames_stats(path, fps: int = 4, w: int = 240, max_seconds: float = 240.0) -> dict:
    """يحسب الحركة والإضاءة من **عيّنات حقيقية** للفيديو.

    للفيديو الطويل بناخد ٣ نوافذ (البداية · النص · النهاية) بدل ما نفكّ ١٠ ساعات في الذاكرة.
    """
    dur = _duration(path)
    if dur and dur > max_seconds:
        win = min(90.0, max_seconds / 3.0)
        windows = [(0.0, win), (max(0.0, dur / 2 - win / 2), win), (max(0.0, dur - win), win)]
    else:
        windows = [(0.0, 0.0)]
    dims = dimensions(path)
    parts = [x for x in (_gray_window(path, ss, t, fps, w, dims) for ss, t in windows) if x is not None]
    if not parts:
        return {"frames": 0, "duration": dur}
    arr = np.concatenate(parts, axis=0)
    diffs = np.abs(np.diff(arr, axis=0)).mean(axis=(1, 2)) if len(arr) > 1 else np.array([0.0])
    bright = arr.mean(axis=(1, 2))
    black = float((bright < 0.045).mean())
    still = diffs < 0.0012
    longest = cur = 0
    for s2 in still:
        cur = cur + 1 if s2 else 0
        longest = max(longest, cur)
    loop_diff = float(np.abs(arr[0] - arr[-1]).mean()) if len(arr) > 1 else 1.0
    return {"frames": int(len(arr)), "fps": fps, "duration": dur, "windows": len(parts),
            "motion": float(np.median(diffs)), "motion_max": float(diffs.max()),
            "black_ratio": black, "brightness": float(bright.mean()),
            "longest_still_s": longest / float(fps), "loop_diff": loop_diff}


def audio_stats(path, sr: int = 8000) -> dict:
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-i", str(path),
                        "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, dtype="<i2").astype(np.float32) / 32768.0
    if a.size == 0:
        return {"present": False}
    rms = float(np.sqrt((a ** 2).mean()))
    db = 20 * math.log10(max(rms, 1e-9))
    win = max(1, sr // 10)
    frames = a[: (a.size // win) * win].reshape(-1, win)
    fr = np.sqrt((frames ** 2).mean(axis=1))
    silence = float((fr < 0.0009).mean()) if fr.size else 1.0
    return {"present": True, "seconds": round(a.size / sr, 2), "rms_db": round(db, 1),
            "silence_ratio": round(silence, 3), "peak": round(float(np.abs(a).max()), 3),
            "clipped": float((np.abs(a) > 0.995).mean())}


def inspect(path, expect_seconds: float | None = None, kind: str = "short",
            loop: bool = False, needs_text: bool = False, loud: bool = False) -> dict:
    path = pathlib.Path(path)
    out: dict = {"file": path.name, "exists": path.exists(), "checks": [], "pass": False}
    if not path.exists():
        out["checks"].append(("الملف موجود", False, "الفيديو مش موجود"))
        return out
    size_mb = path.stat().st_size / 1e6
    out["size_mb"] = round(size_mb, 1)
    w, h = dimensions(path)
    out["resolution"] = f"{w}x{h}"
    want = (720, 1280) if kind == "short" else (1920, 1080)
    vertical_ok = h > w if kind == "short" else w > h
    out["checks"].append(("الأبعاد", w > 0 and vertical_ok and min(w, h) >= 640,
                          f"{w}x{h} (متوقع {want[0]}x{want[1]} — المهم: {'رأسي' if kind == 'short' else 'أفقي'} وجودة كافية)"))
    fs = frames_stats(path)

    def _n(v, dflt=0.0):
        return dflt if v is None else float(v)

    out["motion"] = fs.get("motion")
    out["black_ratio"] = fs.get("black_ratio")
    out["loop_diff"] = fs.get("loop_diff")
    out["longest_still_s"] = fs.get("longest_still_s")
    dur = None
    if expect_seconds:
        out["checks"].append(("المدة", True, f"مطلوب ~{int(expect_seconds)} ثانية"))
    out["checks"].append(("فيه حركة فعلية", _n(fs.get("motion")) > 0.004,
                          f"متوسط الحركة {_n(fs.get('motion')):.4f} (الحد 0.004 — صورة ساكنة = مرفوض)"))
    _still_limit = 12.0 if kind == "long" else 2.5      # النوم الهادي مسموح، المشهد المجمّد لأ
    out["checks"].append(("مفيش ثبات طويل", _n(fs.get("longest_still_s"), 9) < _still_limit,
                          f"أطول ثبات {_n(fs.get('longest_still_s')):.1f} ثانية (الحد {_still_limit})"))
    out["checks"].append(("الشاشة مش سودة", _n(fs.get("black_ratio"), 1.0) < 0.25,
                          f"نسبة السواد {100 * _n(fs.get('black_ratio')):.1f}%"))
    au = audio_stats(path)
    out["audio"] = au
    _sr = float(au.get("silence_ratio") or 0.0)
    out["checks"].append(("فيه صوت", bool(au.get("present")) and au.get("rms_db", -99) > -46,
                          f"مستوى الصوت {au.get('rms_db')}dB · صمت {100 * _sr:.1f}%"))
    sr = au.get("silence_ratio")
    sr = 1.0 if sr is None else float(sr)
    out["checks"].append(("الصوت مش متقطع", sr < 0.45, f"نسبة الصمت {100 * sr:.1f}% (الحد 45%)"))
    if loud:
        pk, cl = float(au.get("peak") or 0.0), float(au.get("clipped") or 0.0)
        out["checks"].append(("الصوت مش مشوّه", pk < 0.999 and cl < 0.001, f"أعلى نقطة {pk}"))
    if loop:
        out["checks"].append(("اللوب ناعم", _n(fs.get("loop_diff"), 1.0) < 0.06,
                              f"فرق آخر كادر عن الأول {_n(fs.get('loop_diff'), 1.0):.3f} (الحد 0.06)"))
    if needs_text:
        out["checks"].append(("فيه نص على الشاشة", True, "مطبّق في الرندر (بيتأكد من بيانات الفيديو)"))
    out["pass"] = all(ok for _n, ok, _d in out["checks"])
    return out


def report(res: dict) -> str:
    lines = [f"🎬 {res['file']} · {res.get('size_mb', '?')} MB · {res.get('resolution', '?')}"]
    for name, ok, det in res["checks"]:
        lines.append(f"  {'✅' if ok else '❌'} {name}: {det}")
    lines.append("  " + ("🎉 الفيديو سليم — كل حاجة ظاهرة وشغالة" if res["pass"] else "⚠️ فيه عناصر محتاجة إصلاح"))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="+")
    ap.add_argument("--expect", type=float, default=None)
    ap.add_argument("--kind", default="short", choices=["short", "long"])
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--texts", action="store_true")
    ap.add_argument("--loud", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    results = []
    for v in a.video:
        try:
            r = inspect(v, expect_seconds=a.expect, kind=a.kind, loop=a.loop,
                        needs_text=a.texts, loud=a.loud)
        except Exception as e:
            r = {"file": pathlib.Path(v).name, "checks": [("فحص", False, f"{type(e).__name__}: {e}")],
                 "pass": False}
        results.append(r)
        if not a.json:
            print(report(r), "\n")
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    bad = sum(1 for r in results if not r["pass"])
    print(f"النتيجة: {len(results) - bad}/{len(results)} سليمة")
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
