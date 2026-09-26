"""
📦 اختبارات نمو المخزون الأساسي (الجيل الثالث والرابع)
=====================================================
بتتأكد إن كل حاجة اتضافت فعلًا وشغالة: مؤثرات صوتية جديدة، مشاهد جديدة،
أنماط موسيقى جديدة، ملصقات جديدة، وقصص جديدة — وكله مسجّل في المكتبة.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np

from engine import cutout, music, sfx, visuals

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ── الجيل الثالث من المؤثرات ──
GEN3_SFX = ("sand_pour", "stone_slide", "snow_crunch", "wood_creak", "leaf_rustle", "water_drip",
            "bird_chirp", "cricket_night", "harp_gliss", "chime_run", "glass_chime_run", "soft_choir",
            "deep_boom", "sparkle_shower", "type_char", "pen_scratch", "clock_chime", "door_soft_close",
            "paper_flip")

# ── الجيل الرابع من المشاهد ──
GEN4_SCENES = ("candle_desk", "zen_garden", "neon_rain", "bubble_lamp")

# ── الجيل الثالث من الموسيقى ──
GEN3_MUSIC = ("city_night", "ocean_lullaby", "glass_garden")

# ── الجيل التالت من الملصقات ──
GEN3_STICKERS = ("leaf", "snowflake", "gem", "gift", "smoke", "butterfly")


def test_gen3_sfx_exist_and_are_alive():
    for name in GEN3_SFX:
        assert name in sfx.SFX, f"مؤثر ناقص: {name}"
        x = sfx.render(name)
        assert x.size > 1000, f"{name} قصير أوي"
        assert float(np.abs(x).max()) > 0.1, f"{name} ساكت"
        assert np.isfinite(x).all(), f"{name} فيه قيم غريبة"


def test_gen3_sfx_are_grouped_and_reachable():
    for group in ("nature", "craft", "cinema"):
        assert group in sfx.USES, f"مجموعة ناقصة: {group}"
        assert len(sfx.USES[group]) >= 5
        for name in sfx.USES[group]:
            assert name in sfx.SFX, f"مجموعة {group} بتشاور على مؤثر مش موجود: {name}"
    # أسماء مجموعات الليل/التركيز/الرضا لسه فيها الجديد
    assert "cricket_night" in sfx.USES["atmosphere"]
    assert "glass_chime_run" in sfx.RECOMMENDED["satisfying"]
    assert sfx.RECOMMENDED["sleep"] == [], "النوم لازم يفضل بلا مؤثرات مفاجئة"
    # كل مؤثر جديد لازم يكون متاح في مجموعة واحدة على الأقل
    reachable = {n for items in list(sfx.USES.values()) + list(sfx.RECOMMENDED.values()) for n in items}
    for name in GEN3_SFX:
        assert name in reachable, f"{name} مش متاح في أي مجموعة"


def test_gen4_scenes_registered_and_seamless():
    for name in GEN4_SCENES:
        assert name in visuals.SCENES, f"مشهد ناقص: {name}"
        sc = visuals.make_scene(name, w=240, h=135, fps=12, seed=4)
        a = sc.raw(0.0)
        b = sc.raw(sc.loop_seconds)
        assert float(np.abs(a - b).max()) < 0.02, f"{name} حلقته فيها قطع"
        mid = sc.raw(sc.loop_seconds * 0.37)
        assert float(np.abs(a - mid).mean()) > 0.0002, f"{name} مش بيتحرك"


def test_gen4_scenes_are_in_stock_pools():
    assert "zen_garden" in visuals.SMILE_SCENES
    assert "bubble_lamp" in visuals.SMILE_SCENES
    for name in ("candle_desk", "neon_rain", "bubble_lamp"):
        assert name in visuals.SLEEP_SCENES


def test_gen3_music_styles_render_steady():
    for style in GEN3_MUSIC:
        assert style in music.STYLES(), f"نمط ناقص: {style}"
        x = music.bed(style, 12.0, seed=5)
        assert abs(x.shape[0] - 12.0 * music.SR) < music.SR * 0.1
        rms = float(np.sqrt((x ** 2).mean()))
        assert 0.03 < rms < 0.30, f"{style} مستواه غريب: {rms}"
        assert float(np.abs(x).max()) <= 0.95


def test_gen3_stickers_on_disk():
    stick = ROOT / "assets" / "stickers"
    for name in GEN3_STICKERS:
        p = stick / f"{name}.png"
        assert p.exists(), f"ملصق ناقص: {name}"
        assert p.stat().st_size > 1200, f"{name} ملفه فاضي"


def test_every_story_character_has_sticker_art():
    doc = json.loads((ROOT / "content" / "stories.json").read_text(encoding="utf-8"))
    missing = set()
    for st in doc["stories"]:
        for beat in st.get("beats", []):
            for ch in beat.get("chars", []):
                who = ch.get("who")
                if who and not (ROOT / "assets" / "stickers" / f"{who}.png").exists():
                    missing.add(who)
    assert not missing, f"شخصيات بلا رسمة: {sorted(missing)}"


def test_library_json_covers_the_growth():
    lib = json.loads((ROOT / "content" / "library.json").read_text(encoding="utf-8"))
    blob = json.dumps(lib, ensure_ascii=False)
    for name in GEN3_SFX + GEN4_SCENES + GEN3_STICKERS:
        assert name in blob, f"{name} مش مسجّل في المكتبة — شغّل tools/build_library.py"
    assert lib["sfx"]["count"] >= 79
    sc = lib["scenes"]
    names = sc if isinstance(sc, list) else [n for v in sc.values() if isinstance(v, list) for n in v] or list(sc)
    assert len(set(names)) >= 16
    assert lib["stickers"]["count"] >= 47


def test_cutout_registry_sees_new_stickers():
    names = set(getattr(cutout, "STICKER_NAMES", set()) or set())
    if names:
        for name in GEN3_STICKERS:
            assert name in names, f"محرك التحريك مش شايف الملصق: {name}"


def test_stock_doc_is_not_stale():
    """المستند لازم يطابق الكود — ممنوع أرقام قديمة أو وهمية."""
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "stock_doc.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
