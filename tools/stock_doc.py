"""
📄 محدّث docs/STOCK.md تلقائيًا من المحركات الحيّة
=================================================
بيقرأ الأرقام من الكود نفسه (sfx · music · fx · visuals · stickers · memes · brand)
ويحدّث جدول المخزون + سطر المجموع في docs/STOCK.md — عشان المستند ما يبقاش كذّاب أبدًا.

    python tools/stock_doc.py            # يحدّث المستند
    python tools/stock_doc.py --check    # يتأكد إن المستند مطابق (للاختبارات/CI)
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import fx, music, sfx, stock, visuals  # noqa: E402

DOC = ROOT / "docs" / "STOCK.md"


def live_counts() -> dict:
    r = stock.report()
    return {
        "sfx": len(sfx.SFX),
        "music": len(music.STYLES()),
        "fx": len(fx.KINDS),
        "scenes": len(visuals.SCENES),
        "scenes_3d": 4,
        "stickers": r["stickers"],
        "memes": r["memes"],
        "brand": r["brand"],
        "total": r["total_assets"],
    }


def render_table(c: dict) -> str:
    rows = [
        "| النوع | العدد | فين | إزاي بيتولّد |",
        "|---|---|---|---|",
        f"| مؤثرات صوتية | **{c['sfx']}** | `assets/sfx/*.wav` + `engine/sfx.py` | تخليق بالكود "
        "(نغمات · ضجيج · رنين · طبيعة · حرفة · سينما) |",
        f"| أنماط موسيقى | **{c['music']}** | `engine/music.py` + `assets/music/*.wav` | أكوردات + لحن + "
        "هواء + موجات، حلقات مقفولة (بلا قطع) |",
        f"| إضافات بصرية (FX) | **{c['fx']}** | `engine/fx.py` | معادلات وقت الرندر (ضوء · غبار · بوكيه · "
        "بلوم · حبيبات …) |",
        f"| مشاهد حيّة | **{c['scenes']}** | `engine/visuals.py` + `engine/render3d.py` | مشاهد 2D و3D "
        f"بتتحرك فعلاً (مش صور) — منهم {c['scenes_3d']} 3D |",
        f"| ملصقات | **{c['stickers']}** | `assets/stickers/*.png` | رسم بالكود + ظل تلامس + تحريك |",
        f"| قوالب ميمز | **{c['memes']}** | `assets/memes/*.png` | رسم بالكود |",
        f"| هوية القناة | **{c['brand']}** | `assets/brand/*.png` | بانر · صورة · endcard · watermark |",
        "",
        f"**المجموع: {c['total']} ملف جاهز** + مخزون لا نهائي (الموسيقى والإضافات والمشاهد بتتحسب "
        "لحظة الطلب).",
    ]
    return "\n".join(rows)


def updated_text(text: str, c: dict) -> str:
    start = text.index("| النوع | العدد |")
    end_marker = "لحظة الطلب)."
    end = text.index(end_marker, start) + len(end_marker)
    return text[:start] + render_table(c) + text[end:]


def main(argv: list[str]) -> int:
    c = live_counts()
    text = DOC.read_text(encoding="utf-8")
    new = updated_text(text, c)
    if "--check" in argv:
        ok = new == text
        print(("✅ المستند مطابق للمخزون" if ok else "⚠️ المستند قديم — شغّل: python tools/stock_doc.py")
              + f" · مؤثرات {c['sfx']} · موسيقى {c['music']} · ملصقات {c['stickers']} · مشاهد {c['scenes']}")
        return 0 if ok else 1
    DOC.write_text(new, encoding="utf-8")
    print(f"✅ docs/STOCK.md اتحدّث من الكود · مؤثرات {c['sfx']} · موسيقى {c['music']} · "
          f"ملصقات {c['stickers']} · مشاهد {c['scenes']} · ميمز {c['memes']} · المجموع {c['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
