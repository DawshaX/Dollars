"""
📦 مخزون المكتبة المحلي — Dollars Studio
=========================================
بيجمّع **المخزون الأساسي** بتاع القناة على الجهاز: كل ملف هنا **ملكنا** (مولّد بالكود)،
يعني المصنع مش محتاج نت ولا ترخيص ولا إذن حد — يشتغل من المخزون ده للأبد.

    python engine/stock.py --all        # يبني كل حاجة (أصوات + موسيقى + فهرس)
    python engine/stock.py --sfx        # المؤثرات الصوتية
    python engine/stock.py --music      # عيّنات الموسيقى بتاعتنا
    python engine/stock.py --report     # تقرير المخزون

المخزون:
    assets/sfx/      60 مؤثر صوتي (توليف رقمي)
    assets/music/    عيّنات من كل نمط موسيقى (الموسيقى نفسها بتتولّد بلا حدود وقت الطلب)
    assets/stickers/ 36 ملصق + assets/memes/ 6 قوالب
    assets/brand/    هوية القناة كاملة
    engine/fx.py     10 إضافات بصرية (معادلات — مخزون لا نهائي)
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))          # عشان يشتغل من أي مكان
ASSETS = ROOT / "assets"


def _rel(p: pathlib.Path) -> str:
    return str(pathlib.Path(p).relative_to(ROOT))


def build_sfx(out_dir=None) -> dict:
    """يرسم كل المؤثرات (60) كملفات WAV محلية + فهرس."""
    from engine import sfx
    out = pathlib.Path(out_dir or (ASSETS / "sfx"))
    t0 = time.time()
    made = sfx.build_all(str(out))
    total = sum(p.stat().st_size for p in out.glob("*.wav"))
    return {"count": len(made), "files": [p.name for p in sorted(out.glob("*.wav"))],
            "mb": round(total / 1048576, 2), "seconds": round(time.time() - t0, 1)}


def build_music(styles: str = "previews", seconds: float = 6.0, sr_out: int = 22050) -> dict:
    """عيّنات قصيرة (**أحادية 22kHz** = خفيفة على المستودع) — الموسيقى الكاملة بتتولّد وقت الطلب."""
    import wave

    import numpy as np

    from engine import music
    out = ASSETS / "music"
    out.mkdir(parents=True, exist_ok=True)
    made = {}
    for i, style in enumerate(music.STYLES()):
        x = music.bed(style, seconds, seed=101 + i * 7)           # 44.1k ستيريو
        mono = ((x[:, 0] + x[:, 1]) * 0.5)                        # نحوّل لأحادي
        step = max(1, int(music.SR / sr_out))
        mono = mono[::step]                                       # تقليل معدّل العينات
        pcm = (np.clip(mono, -1, 1) * 32767).astype("<i2")
        p = out / f"{style}.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr_out)
            w.writeframes(pcm.tobytes())
        made[style] = _rel(p)
    (out / "index.json").write_text(json.dumps(
        {"note": "عيّنات من الموسيقى اللي بنعملها بالكود — كل نمط حلقة مقفولة بتتكرر بلا قطع.",
         "styles": music.STYLES(), "files": made, "sample_seconds": seconds},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return made


def count_dir(name: str, pattern: str = "*") -> int:
    p = ASSETS / name
    return len([f for f in p.glob(pattern) if f.is_file()]) if p.exists() else 0


def report() -> dict:
    from engine import fx, music, sfx, visuals
    d = {
        "sfx": count_dir("sfx", "*.wav"),
        "music_styles": len(music.STYLES()),
        "music_previews": count_dir("music", "*.wav"),
        "stickers": count_dir("stickers", "*.png"),
        "memes": count_dir("memes", "*.png"),
        "brand": count_dir("brand", "*.png"),
        "visual_fx": len(fx.KINDS),
        "scenes": len(visuals.SCENES),
        "2d_scenes": len(visuals.SCENES) - len([s for s in visuals.SCENES if s in ("valley_lake", "snow_pines", "dunes_moon", "planet_rings")]),
    }
    d["total_assets"] = d["sfx"] + d["music_previews"] + d["stickers"] + d["memes"] + d["brand"]
    return d


def build_all() -> dict:
    """يبني المخزون كامل + يحدّث فهرس المكتبة (content/library.json)."""
    sfx_info = build_sfx()
    music_map = build_music()
    (ASSETS / "stock.json").write_text(json.dumps({
        "note": "المخزون المحلي الأساسي — كل ملف هنا ملكنا (مولّد بالكود) ⇒ صفر حقوق، صفر سرقة.",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sfx": sfx_info["count"], "sfx_mb": sfx_info["mb"], "music_previews": list(music_map),
        "fx_kinds": __import__("engine.fx", fromlist=["KINDS"]).KINDS,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    try:                                        # نحدّث فهرس المكتبة الكبير
        import subprocess
        import sys
        subprocess.run([sys.executable, str(ROOT / "tools" / "build_library.py")], check=True,
                       capture_output=True)
    except Exception:
        pass
    return report()


def text_report() -> str:
    r = report()
    rows = ["📦 مخزون المكتبة (محلي · ملكنا · بلا حقوق)", ""]
    rows += [f"• مؤثرات صوتية: **{r['sfx']}** ملف",
             f"• أنماط موسيقى: **{r['music_styles']}** (عيّنات محفوظة: {r['music_previews']})",
             f"• ملصقات: **{r['stickers']}** · ميمز: **{r['memes']}**",
             f"• هوية القناة: **{r['brand']}** صورة",
             f"• إضافات بصرية (FX): **{r['visual_fx']}** نوع",
             f"• مشاهد حيّة: **{r['scenes']}** (منهم 3D: 4)",
             "",
             f"**إجمالي الملفات الجاهزة: {r['total_assets']}** + مخزون لا نهائي (موسيقى/FX/مشاهد بتتولّد وقت الطلب)"]
    return "\n".join(rows)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="مخزون المكتبة المحلي")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--sfx", action="store_true")
    ap.add_argument("--music", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.sfx:
        print("✅ أصوات:", build_sfx())
    if a.music:
        print("✅ موسيقى:", list(build_music()))
    if a.all:
        r = build_all()
        print(text_report())
    if a.report or not (a.all or a.sfx or a.music):
        print(text_report())
