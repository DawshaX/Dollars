"""
📚 يبني فهرس المكتبة الكامل (content/library.json) — كل حاجة ملكنا ومرخّصة لنا.
يستخدمه المجمّع عشان يعرف: إيه المتاح · إيه استخدامه · وإيه الحدود.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import ambient, sfx, visuals  # noqa: E402


def _load(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def build() -> dict:
    sfx_index = _load(ROOT / "assets/sfx/index.json", {})
    stick = _load(ROOT / "assets/stickers/index.json", {})
    memes = _load(ROOT / "assets/memes/index.json", {})
    chars = _load(ROOT / "content/characters.json", {"characters": []})
    lib = {
        "note": "مكتبة Dollars — كل عنصر هنا ملكنا (متولّد بالكود) ⇒ صفر حقوق، صفر سرقة.",
        "license": "owned-generated",
        "version": 20260925,
        "scenes": {
            "long_ambience": list(visuals.SLEEP_SCENES),
            "satisfying_and_stingers": list(visuals.SMILE_SCENES),
            "all": sorted(visuals.SCENES),
            "note": "كل مشهد حركة حقيقية (جزيئات · موج · لهب · كور) مش صورة ثابتة",
        },
        "audio_recipes": sorted({
            "sleep_rain": "مطر + رعد بعيد + همهمة غرفة",
            "rain_only": "مطر صافي",
            "ocean": "موج + ريح",
            "storm": "عاصفة كاملة",
            "fireplace": "نار + همهمة",
            "focus": "ضجيج بنّي + ريح خفيفة",
            "calm_night": "ليل هادي",
            "meditation": "نبض قلب + همهمة",
        }),
        "sfx": {"count": sfx_index.get("count", 0), "uses": sfx_index.get("uses", {}),
                "recommended": sfx_index.get("recommended", {})},
        "stickers": {"count": stick.get("count", 0), "uses": stick.get("uses", {})},
        "memes": {"count": len(memes.get("templates", {})), "templates": memes.get("templates", {})},
        "characters": [{"id": c["id"], "name": c["name"], "type": c.get("type"),
                        "origin": c.get("origin", "hand")} for c in chars.get("characters", [])],
        "rules": {
            "no_copyright": "ممنوع أي مقطع/صورة/أغنية/ميم من حد تاني — ولو مشهور",
            "no_real_people_voices": "ممنوع تقليد صوت أي إنسان حقيقي",
            "ai_disclosure": "الإفصاح عن المحتوى المولّد إلزامي في كل وصف",
            "not_made_for_kids": "family-safe لكن مش «مصنوع للأطفال» (عشان الإعلانات)",
            "allowed_external": ["NASA (ملكية عامة)", "Wikimedia CC0", "Pexels/Pixabay (بسجل ترخيص)",
                                 "Openverse (CC0 فقط) — وممنوع أي حاجة CC BY-NC"],
            "log_required": "أي أصل خارجي لازم يتسجّل في vault/index.json بالترخيص والمصدر",
        },
        "how_to_use": {
            "sleep_long": "مشهد نوم + وصفة صوت + شاشة سوداء اختياري ⇒ 3/8/10 ساعات",
            "story": "شخصية + مشهد + مؤثرات (bell/appear/boing/sparkle) + ملصقات المشاعر",
            "satisfying_short": "مشهد رياضي (sand_table/pendulum_wave/harmonograph) + pops/clicks",
            "transitions": "whoosh · swipe · glitch · zoom · ink wipe بين المشاهد",
        },
    }
    return lib


def main():
    lib = build()
    out = ROOT / "content/library.json"
    out.write_text(json.dumps(lib, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ الفهرس اتكتب: {out} · مشاهد {len(lib['scenes']['all'])} · "
          f"مؤثرات {lib['sfx']['count']} · ملصقات {lib['stickers']['count']} · "
          f"قوالب ميمز {lib['memes']['count']} · شخصيات {len(lib['characters'])}")


if __name__ == "__main__":
    main()
