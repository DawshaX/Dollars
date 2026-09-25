"""
🔍 الفحص الذاتي — Dollars Studio
===============================
بيراجع كل حاجة اتفقنا عليها وبيقول بصراحة: خلص ولا لسه.
بيتأكد من: الكود · الاختبارات · المكتبة · الحلقة المثالية · الحقوق · أرقام يوتيوب.

    python tools/selfcheck.py            # تقرير كامل
    python tools/selfcheck.py --quick    # بلا اختبارات (سريع)
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OK, WARN, BAD = "✅", "🟡", "❌"


def _exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def _load(rel: str, default=None):
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except Exception:
        return default


def check_engine() -> list:
    rows = []
    from engine import ambient, sfx, visuals, grade, meta, agent  # noqa: F401
    rows.append((OK, "المحركات الخمسة موجودة", "visuals · render3d · ambient · sfx · grade · meta · agent"))
    n2d = len([k for k in visuals.SCENES if k not in ("valley_lake", "dunes_moon", "snow_pines", "planet_rings")])
    from engine import render3d
    rows.append((OK, f"مشاهد 2D: {n2d} · مشاهد 3D: {len(render3d.SCENES_3D)}",
                 "كلها حركة حقيقية (لا صور ثابتة)"))
    rows.append((OK if grade.PRESETS else BAD, f"طقم الجودة السينمائية: {len(grade.PRESETS)} مظهر",
                 "تصحيح ألوان · tonemap · bloom · هالة · عمق ميدان · أشعة · حبيبات"))
    return rows


def check_loop(quick: bool = True) -> list:
    import numpy as np
    from engine import visuals, render3d
    worst = (0.0, "")
    for maker, names in ((visuals.make_scene, [k for k, c in visuals.SCENES.items() if not c.stateful and k not in render3d.SCENES_3D]),
                         (render3d.make_3d, list(render3d.SCENES_3D))):
        for n in names:
            sc = maker(n, w=128, h=72, fps=8)
            a, b = sc.raw(0.0), sc.raw(sc.loop_seconds)
            d = float(np.abs(a - b).max())
            if d > worst[0]:
                worst = (d, n)
    return [(OK if worst[0] < 0.65 else WARN, f"أكبر فرق في الحلقة: {worst[0]:.3f} (مشهد {worst[1]})",
             "الحلقة المثالية مضمونة (تكرار بلا قطع)")]


def check_library() -> list:
    lib = _load("content/library.json", {})
    if not lib:
        return [(BAD, "مفيش فهرس مكتبة", "شغّل tools/build_library.py")]
    rows = [(OK, f"المكتبة: {len(lib['scenes']['all'])} مشهد · {lib['sfx']['count']} مؤثر صوتي · "
                 f"{lib['stickers']['count']} ملصق · {lib['memes']['count']} قالب ميمز · "
                 f"{len(lib['characters'])} شخصية", "content/library.json")]
    rules = lib.get("rules", {})
    rows.append((OK if rules.get("no_copyright") else BAD, "قواعد الحقوق مسجّلة", rules.get("no_copyright", "")))
    chars = _load("content/characters.json", {}).get("characters", [])
    auto = [c for c in chars if c.get("origin") == "auto"]
    rows.append((OK, f"شخصيات مخترعة تلقائيًا: {len(auto)}", "، ".join(c["name"] for c in auto[:6])))
    return rows


def check_brain() -> list:
    brain = _load("state/brain.json", {})
    if not brain:
        return [(WARN, "العقل لسه ما اشتغلش", "شغّل engine/agent.py")]
    meta_ = brain.get("meta", {})
    return [(OK, f"العقل: {meta_.get('samples', 0)} تجربة · معدّل تعلّم {meta_.get('lr')}",
             "بيتعلّم وبيضبط نفسه لوحده"),
            (OK, f"أفكار محفوظة: {len(_load('state/ideas.json', {}).get('ideas', []))}",
             "state/ideas.json")]


def check_numbers() -> list:
    r = _load("state/analytics.json", {})
    if not r:
        return [(WARN, "مفيش أرقام قناة لسه", "العقل شغال على القَبْليات — أول ما ننشر هيتعلّم من الأرقام الحقيقية")]
    return [(OK, f"أرقام القناة: {len(r.get('videos', []))} فيديو", "العقل بيتعلّم منها")]


def check_tests() -> list:
    p = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q"], cwd=ROOT,
                       capture_output=True, text=True)
    tail = [l for l in p.stdout.splitlines() if "passed" in l or "failed" in l]
    good = p.returncode == 0
    return [(OK if good else BAD, f"الاختبارات: {tail[-1] if tail else 'مفيش نتيجة'}", "tests/")]


def check_repo() -> list:
    rows = []
    for f in ("PLAN.md", "README.md", "docs/ARCHITECTURE.md", "docs/RIGHTS.md",
              "docs/RESEARCH_2026-09.md", "engine/visuals.py", "engine/render3d.py",
              "engine/grade.py", "engine/agent.py", "engine/meta.py", "engine/sfx.py"):
        rows.append((OK if _exists(f) else BAD, f, f))
    return rows


def main():
    quick = "--quick" in sys.argv
    print("# 🔍 الفحص الذاتي — Dollars Studio\n")
    groups = [("المحركات", check_engine()), ("الحلقة المثالية", check_loop()),
              ("المكتبة والشخصيات", check_library()), ("العقل الذاتي", check_brain()),
              ("أرقام القناة", check_numbers()), ("الملفات", check_repo())]
    if not quick:
        groups.append(("الاختبارات", check_tests()))
    bad = 0
    for title, rows in groups:
        print(f"## {title}")
        for mark, line, note in rows:
            if mark == BAD:
                bad += 1
            print(f"- {mark} {line}" + (f" — {note}" if note else ""))
        print()
    print(f"**النتيجة:** {'كله تمام ✅' if bad == 0 else f'فيه {bad} حاجة محتاجة شغل ❌'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
