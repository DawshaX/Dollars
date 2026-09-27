"""📊 تحليلات عميقة — Dollars Studio

يسأل يوتيوب عن الأرقام اللي **مش** في الـAPI العام: الظهور (impressions) · نسبة النقر ·
مدة المشاهدة · من فين المشاهدين · أي فيديو اتشاف وأي فيديو لأ.

    python tools/analytics_deep.py             # آخر ٢٨ يوم
    python tools/analytics_deep.py --days 7 --telegram

⚠️ لو طلع خطأ صلاحية (403) ⇒ معنى كده إن توكن القناة مش معاه صلاحية التحليلات،
وساعتها لازم موافقة جديدة من صاحب القناة (رابط واحد) — الأداة بتقول كده صراحة.
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

sys.path[:] = [q for q in sys.path if pathlib.Path(q or ".").resolve() != pathlib.Path(__file__).resolve().parent]
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import publish  # noqa: E402

YTA = "https://youtubeanalytics.googleapis.com/v2/reports"


def _call(tok: str, params: dict) -> tuple[dict | None, str]:
    url = f"{YTA}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8")), ""
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode("utf-8"))
            return None, f"{e.code}: " + str((j.get("error") or {}).get("message"))[:160]
        except Exception:
            return None, f"{e.code}"
    except Exception as e:
        return None, type(e).__name__


def run(days: int = 28) -> dict:
    tok = None
    for prj in publish.all_projects():
        try:
            tok = publish.access_token(prj)
            if tok:
                break
        except Exception:
            continue
    if not tok:
        return {"ok": False, "reason": "مفيش توكن قناة"}
    end = date.today()
    start = end - timedelta(days=max(1, days))
    base = {"ids": "channel==MINE", "startDate": start.isoformat(), "endDate": end.isoformat()}
    out: dict = {"ok": True, "from": start.isoformat(), "to": end.isoformat(), "parts": {}}
    # 1) إجماليات القناة (مشاهدات · دقايق · مشتركين)
    tot, err = _call(tok, {**base, "metrics": "views,estimatedMinutesWatched,subscribersGained,subscribersLost"})
    out["parts"]["totals"] = tot or {"error": err}
    # 2) الظهور ونسبة النقر (لو الصلاحية تسمح)
    imp, err2 = _call(tok, {**base, "metrics": "impressions,impressionClickThroughRate"})
    out["parts"]["impressions"] = imp or {"error": err2}
    # 3) كل فيديو لوحده
    per, err3 = _call(tok, {**base, "metrics": "views,estimatedMinutesWatched,averageViewDuration,subscribersGained",
                            "dimensions": "video", "sort": "-views", "maxResults": "25"})
    out["parts"]["per_video"] = per or {"error": err3}
    # 4) الدول
    geo, err4 = _call(tok, {**base, "metrics": "views", "dimensions": "country", "sort": "-views",
                            "maxResults": "12"})
    out["parts"]["countries"] = geo or {"error": err4}
    out["scope_ok"] = not any(str((out["parts"][k] or {}).get("error", "")).startswith("403")
                              for k in out["parts"])
    return out


def report(d: dict) -> str:
    if not d.get("ok"):
        return "❌ تحليلات: " + str(d.get("reason"))
    L = [f"📊 تحليلات القناة ({d['from']} → {d['to']})"]
    t = d["parts"].get("totals") or {}
    if t.get("rows"):
        r = t["rows"][0]
        L.append(f"👁️ مشاهدات {r[0]:,} · ⏱️ {r[1]:,} دقيقة · ➕ مشتركين {r[2]} · ➖ {r[3]}")
    else:
        L.append("إجماليات: " + str(t.get("error") or "مفيش بيانات"))
    im = d["parts"].get("impressions") or {}
    if im.get("rows"):
        r = im["rows"][0]
        L.append(f"🚀 ظهور {r[0]:,} · نسبة النقر {r[1]:.1%}")
    else:
        L.append("🚀 الظهور: " + str(im.get("error") or "مش متاح"))
    g = (d["parts"].get("countries") or {}).get("rows") or []
    if g:
        L.append("🌍 أكثر البلاد: " + " · ".join(f"{c[0]} {c[1]:,}" for c in g[:6]))
    pv = (d["parts"].get("per_video") or {}).get("rows") or []
    if pv:
        L.append("🎬 أعلى الفيديوهات:")
        for r in pv[:6]:
            L.append(f"   {r[1]:,} مشاهدة · {int(r[2])}ث متوسط · {r[0]}")
    if not d.get("scope_ok"):
        L.append("⚠️ التوكن مش معاه صلاحية التحليلات — محتاجين موافقة جديدة (رابط واحد).")
    return "\n".join(L)


def main() -> int:
    days = 28
    if "--days" in sys.argv:
        i = sys.argv.index("--days")
        days = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 28
    d = run(days)
    txt = report(d)
    print(txt)
    try:
        (ROOT / "state" / "analytics_deep.json").write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                                           encoding="utf-8")
    except Exception:
        pass
    if "--telegram" in sys.argv:
        try:
            print("📨 تليجرام:", "اتبعت" if publish.notify("📊 Dollars · تحليلات\n\n" + txt[:3500]) else "فشل")
        except Exception as e:
            print("📨 تليجرام: فشل —", type(e).__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
