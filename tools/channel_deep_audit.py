#!/usr/bin/env python3
"""
🔍 تشريح القناة — Dollars Studio
================================
بيجاوب على السؤال الحقيقي: **ليه مفيش مشاهدات؟** بالأرقام من يوتيوب نفسه:

    • كل فيديوهات القناة (٣٣١) بمشاهداتها وتاريخ نشرها
    • المشاهدات محسوبة لكل يوم / أسبوع / شهر ⇒ نشوف لحظة الانهيار بالظبط
    • أحسن ٢٥ فيديو (اللي جابوا مشاهدات) وصفاتهم: العنوان · المدة · النوع · عمره
    • مقارنة «قبل/بعد»: أسلوب الإنتاج القديم ضد الجديد
    • توزيع الرفع اليومي (كام فيديو في اليوم) قصاد المشاهدات اللي جت
    • حالات الرفع: public/processed/مرفوض/أطفال

    python tools/channel_deep_audit.py            # تقرير كامل
    python tools/channel_deep_audit.py --telegram # + إرسال الملخّص على تليجرام
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "state" / "deep_audit.json"


def api(url: str, token: str) -> dict:
    import urllib.request
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _secs(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


# 🏭 قنوات المصانع: الدولارز (قناتنا) + نور الإسلامية (مصنع XTreNDAW)
CHANNELS = [
    ("الدولارز — xDaw NoVa", ""),                       # فارغ = قناتنا المربوطة بالتوكن
    ("نور — XTreNDAW ShOrts", "UC2PCynDtd_wtPrgoAuqH6yw"),
]


def collect(max_videos: int = 600, channel_id: str = "") -> dict:
    from engine import publish
    token = publish.access_token()
    u = "https://www.googleapis.com/youtube/v3/channels?part=contentDetails,statistics,snippet"
    u += f"&id={channel_id}" if channel_id else "&mine=true"
    ch = api(u, token)
    it = (ch.get("items") or [{}])[0]
    upl = ((it.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads", "")
    # كل الفيديوهات (playlistItems ٥٠ لكل صفحة)
    ids, page = [], ""
    while len(ids) < max_videos:
        u = f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=50&playlistId={upl}"
        if page:
            u += f"&pageToken={page}"
        d = api(u, token)
        ids += [i["contentDetails"]["videoId"] for i in (d.get("items") or [])]
        page = d.get("nextPageToken") or ""
        if not page:
            break
    rows = []
    for i in range(0, len(ids), 50):                      # تفاصيل كل فيديو
        chunk = ",".join(ids[i:i + 50])
        d = api("https://www.googleapis.com/youtube/v3/videos"
                f"?part=snippet,statistics,contentDetails,status,localizations&id={chunk}", token)
        for v in (d.get("items") or []):
            s, st, cd, sst = (v.get("snippet") or {}), (v.get("statistics") or {}), \
                             (v.get("contentDetails") or {}), (v.get("status") or {})
            rows.append({
                "id": v.get("id"), "at": (s.get("publishedAt") or "")[:19],
                "title": s.get("title") or "", "dur": cd.get("duration") or "",
                "secs": _secs(cd.get("duration") or ""), "views": int(st.get("viewCount") or 0),
                "likes": int(st.get("likeCount") or 0), "comments": int(st.get("commentCount") or 0),
                "privacy": sst.get("privacyStatus") or "?", "upload": sst.get("uploadStatus") or "?",
                "reject": sst.get("rejectionReason") or "", "kids": bool(sst.get("madeForKids")),
                "lang": s.get("defaultLanguage") or "—",
                "loc": len((v.get("localizations") or {})),
            })
    return {"channel": {"title": (it.get("snippet") or {}).get("title"),
                        "subs": int((it.get("statistics") or {}).get("subscriberCount") or 0),
                        "videos": int((it.get("statistics") or {}).get("videoCount") or 0),
                        "views": int((it.get("statistics") or {}).get("viewCount") or 0)},
            "rows": rows}


def short(row: dict) -> bool:
    return row["secs"] <= 65 or "#short" in row["title"].lower()


def analyze(data: dict) -> dict:
    rows = sorted(data["rows"], key=lambda r: r["at"])
    now = datetime.now(timezone.utc)
    out: dict = {"channel": data["channel"], "total": len(rows)}

    def day(r):  return r["at"][:10]
    def month(r): return r["at"][:7]

    by_month: dict[str, dict] = defaultdict(lambda: {"n": 0, "views": 0, "zero": 0})
    for r in rows:
        m = by_month[month(r)]
        m["n"] += 1
        m["views"] += r["views"]
        m["zero"] += 1 if r["views"] == 0 else 0
    out["by_month"] = {k: dict(v) for k, v in sorted(by_month.items())}

    by_day: dict[str, dict] = defaultdict(lambda: {"n": 0, "views": 0})
    for r in rows:
        d = by_day[day(r)]
        d["n"] += 1
        d["views"] += r["views"]
    out["by_day"] = {k: dict(v) for k, v in sorted(by_day.items())}

    # أحسن الفيديوهات (اللي جابت مشاهدات فعلًا)
    top = sorted(rows, key=lambda r: -r["views"])[:25]
    out["top"] = [{"id": r["id"], "at": r["at"], "views": r["views"], "secs": r["secs"],
                   "likes": r["likes"], "comments": r["comments"], "title": r["title"],
                   "age_days": round((now - datetime.fromisoformat(r["at"] + "+00:00")).days, 1)}
                  for r in top]

    # آخر ٧ أيام / ٤٨ ساعة: اللي بيشتغل *دلوقتي*
    def since(hours):
        cut = now - timedelta(hours=hours)
        sel = [r for r in rows if r["at"] and datetime.fromisoformat(r["at"] + "+00:00") >= cut]
        return {"n": len(sel), "views": sum(r["views"] for r in sel),
                "with_views": sum(1 for r in sel if r["views"] > 0),
                "best": max((r["views"] for r in sel), default=0)}
    out["last_24h"], out["last_48h"], out["last_7d"] = since(24), since(48), since(24 * 7)

    # شورتس ضد طويل
    sh = [r for r in rows if short(r)]
    lg = [r for r in rows if not short(r)]
    out["shorts"] = {"n": len(sh), "views": sum(r["views"] for r in sh),
                     "zero": sum(1 for r in sh if r["views"] == 0),
                     "median": sorted(r["views"] for r in sh)[len(sh) // 2] if sh else 0}
    out["longs"] = {"n": len(lg), "views": sum(r["views"] for r in lg),
                    "zero": sum(1 for r in lg if r["views"] == 0),
                    "median": sorted(r["views"] for r in lg)[len(lg) // 2] if lg else 0}

    # حالات الرفع
    out["status"] = {"privacy": dict(Counter(r["privacy"] for r in rows)),
                     "upload": dict(Counter(r["upload"] for r in rows)),
                     "rejected": [r["id"] for r in rows if r["reject"]][:20],
                     "kids": sum(1 for r in rows if r["kids"]),
                     "with_locales": sum(1 for r in rows if r["loc"])}

    # معدّل النشر اليومي مقابل المشاهدات (آخر ١٤ يوم)
    days = sorted(by_day)[-14:]
    out["rate_vs_views"] = [{"day": d, "uploaded": by_day[d]["n"], "views": by_day[d]["views"]} for d in days]

    # أنماط العنوان في اللي جاب مشاهدات (عشان نعرف إيه اللي بيشتغل)
    pat = Counter()
    for r in top:
        t = r["title"].lower()
        pat["#shorts" if "#short" in t else "no-hashtag"] += 1
        pat["duration<=20s" if r["secs"] <= 20 else ("20-60s" if r["secs"] <= 65 else "long")] += 1
        for kw in ("sleep", "rain", "study", "kinetic", "story", "fact", "asmr", "satisfying",
                   "ocean", "space", "cat", "dog"):
            if kw in t:
                pat[kw] += 1
    out["winning_patterns"] = dict(pat)
    return out


def report(a: dict) -> str:
    L = []
    c = a["channel"]
    L.append(f"🔍 تشريح القناة: {c['title']} · {c['subs']} مشترك · {c['videos']} فيديو · {c['views']:,} مشاهدة كلية")
    L.append("─" * 60)
    L.append("📅 المشاهدات لكل شهر (عدد الفيديوهات · المشاهدات · اللي جاب صفر):")
    for m, v in a["by_month"].items():
        L.append(f"   {m}: {v['n']:>4} فيديو · {v['views']:>7,} مشاهدة · صفر: {v['zero']:>3}")
    L.append("─" * 60)
    L.append(f"⚡ آخر ٢٤ ساعة: {a['last_24h']['n']} فيديو · {a['last_24h']['views']} مشاهدة "
             f"(فيهم مشاهدات: {a['last_24h']['with_views']}) · أحسن واحد: {a['last_24h']['best']}")
    L.append(f"⚡ آخر ٤٨ ساعة: {a['last_48h']['n']} فيديو · {a['last_48h']['views']} مشاهدة")
    L.append(f"⚡ آخر ٧ أيام: {a['last_7d']['n']} فيديو · {a['last_7d']['views']} مشاهدة "
             f"· فيهم مشاهدات: {a['last_7d']['with_views']}")
    L.append("─" * 60)
    L.append(f"🎬 شورتس: {a['shorts']['n']} · مشاهدات {a['shorts']['views']:,} · صفر {a['shorts']['zero']} "
             f"· وسيط {a['shorts']['median']}")
    L.append(f"🎥 طويلة: {a['longs']['n']} · مشاهدات {a['longs']['views']:,} · صفر {a['longs']['zero']} "
             f"· وسيط {a['longs']['median']}")
    L.append("─" * 60)
    L.append("🏆 أحسن ١٢ فيديو (اللي بيشتغل فعلًا):")
    for r in a["top"][:12]:
        L.append(f"   {r['views']:>6,} 👁 · {r['secs']:>4}s · عمره {r['age_days']:>5} يوم · {r['title'][:58]}")
    L.append("─" * 60)
    L.append(f"🧬 أنماط الرابحين: {a['winning_patterns']}")
    L.append(f"🩺 حالات الرفع: privacy={a['status']['privacy']} · upload={a['status']['upload']} "
             f"· مرفوض: {len(a['status']['rejected'])} · أطفال: {a['status']['kids']} "
             f"· بنسخ لغوية: {a['status']['with_locales']}")
    L.append("─" * 60)
    L.append("📈 معدّل النشر اليومي مقابل المشاهدات (آخر ١٤ يوم):")
    for d in a["rate_vs_views"]:
        bar = "█" * min(40, d["views"] // 20) or "·"
        L.append(f"   {d['day']} · رُفع {d['uploaded']:>3} · مشاهدات {d['views']:>6,} {bar}")
    return "\n".join(L)


def main() -> int:
    import os
    only = (os.environ.get("DOLLARS_AUDIT_CHANNEL") or "").strip()
    parts = []
    for name, cid in CHANNELS:
        if only and cid != only:
            continue
        try:
            a = analyze(collect(channel_id=cid))
            a["channel"]["label"] = name
            parts.append(a)
            print(report(a)); print()
        except Exception as e:
            print(f"⚠️ قناة {name}: اتعذّر ({type(e).__name__}: {str(e)[:80]})")
    if not parts:
        print("مفيش قنوات اتفحصت")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"channels": parts}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"💾 اتحفظ: {OUT}")
    if "--telegram" in sys.argv:
        try:
            from engine import publish
            msg = "🔍 تشريح المصانع (أرقام حقيقية)\n" + "\n".join(
                f"• {a['channel'].get('label')}: {a['channel']['subs']} مشترك · "
                f"آخر ٧ أيام {a['last_7d']['n']} فيديو ⇒ {a['last_7d']['views']} مشاهدة"
                for a in parts)
            ok = publish.notify(msg)
            print("📨 تليجرام:", "اتبعت ✅" if ok else "مش مفعّل")
        except Exception as e:
            print("📨 تليجرام اتعذّر:", type(e).__name__)
    return 0


def _old_main() -> int:
    data = collect()
    a = analyze(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    txt = report(a)
    print(txt)
    print(f"\n💾 اتحفظ: {OUT}")
    if "--telegram" in sys.argv:
        try:
            from engine import publish
            ok = publish.notify("🔍 تشريح القناة (أرقام حقيقية)\n" + txt[:3500])
            print("📨 تليجرام:", "اتبعت ✅" if ok else "مش مفعّل")
        except Exception as e:
            print("📨 تليجرام اتعذّر:", type(e).__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
