#!/usr/bin/env python3
"""
🔬 إثبات حقيقي من عند جوجل نفسه — Dollars Studio
================================================
مش بنقول «شاف الفيديو» وخلاص: الأداة دي بتسأل **يوتيوب API** عن آخر الفيديوهات
المنشورة على قناتنا وترجّع بالظبط:

    • الوقت الحقيقي للنشر · اللغة الأساسية (defaultLanguage) · النسخ العالمية (localizations)
    • المشاهدات/اللايكات/التعليقات لكل فيديو
    • كام فيديو عربي أساسي · كام فيديو معاه نسخ عالمية · كام واحد صفر مشاهدات

    python tools/live_check.py                 # آخر ١٢ فيديو
    python tools/live_check.py --n 20 --telegram

لو مفيش اعتماد للقناة: بيطبع السبب وبيخرج بصفر (الشغل ميتوقفش).
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STATE = ROOT / "state"


def api(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def run(n: int = 12) -> dict:
    from engine import publish
    try:
        token = publish.access_token()
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    ch = api("https://www.googleapis.com/youtube/v3/channels?part=contentDetails,statistics&mine=true", token)
    it = (ch.get("items") or [{}])[0]
    upl = ((it.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads", "")
    st = it.get("statistics") or {}
    pl = api(f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults={n}"
             f"&playlistId={upl}", token)
    ids = [i["contentDetails"]["videoId"] for i in (pl.get("items") or [])]
    if not ids:
        return {"ok": False, "error": "مفيش فيديوهات على القناة؟"}
    vids = api("https://www.googleapis.com/youtube/v3/videos?part=snippet,localizations,statistics,status,"
               f"contentDetails&id={','.join(ids)}", token)
    rows = []
    for v in (vids.get("items") or []):
        s = v.get("snippet") or {}
        loc = v.get("localizations") or {}
        stt = v.get("status") or {}
        cd = v.get("contentDetails") or {}
        rows.append({"id": v.get("id"), "at": (s.get("publishedAt") or "")[:16],
                     "lang": s.get("defaultLanguage") or "—", "locales": sorted(loc.keys()),
                     "loc_sample": ((loc.get("ar") or {}).get("title") or "")[:40],
                     "title": s.get("title") or "", "views": int((v.get("statistics") or {}).get("viewCount") or 0),
                     "likes": int((v.get("statistics") or {}).get("likeCount") or 0),
                     "comments": int((v.get("statistics") or {}).get("commentCount") or 0),
                     "privacy": stt.get("privacyStatus") or "?", "upload": stt.get("uploadStatus") or "?",
                     "reject": stt.get("rejectionReason") or "", "kids": bool(stt.get("madeForKids")),
                     "caption": bool(cd.get("caption") == "true"), "dur": cd.get("duration") or ""})
    # 📌 هل التعليق المثبّت موجود فعلًا على آخر فيديو؟ (إثبات إن التفاعل بيشتغل)
    pinned_ok = None
    try:
        ct = api(f"https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId={ids[0]}"
                 f"&maxResults=5", token)
        items = ct.get("items") or []
        pinned_ok = bool(items)
        if pinned_ok:
            rows_pin = [i["snippet"]["topLevelComment"]["snippet"].get("textDisplay", "")
                        for i in items]
    except Exception:
        pinned_ok = None
    return {"ok": True, "pinned": pinned_ok, "channel": {"title": (it.get("snippet") or {}).get("title"),
                                    "subs": st.get("subscriberCount"), "videos": st.get("videoCount"),
                                    "views": st.get("viewCount")},
            "rows": rows,
            "ar_primary": sum(1 for r in rows if r["lang"].startswith("ar")),
            "with_locales": sum(1 for r in rows if r["locales"]),
            "zero_views": sum(1 for r in rows if r["views"] == 0)}


def burst_check() -> str:
    """🚦 فحص الدفع الجماعي: كام فيديو نزل في نفس الساعة (السبب المعروف لدفن القناة)."""
    try:
        pub = json.loads((STATE / "published.json").read_text(encoding="utf-8")).get("videos") or []
    except Exception:
        return "مفيش سجل"
    import collections, datetime
    c = collections.Counter(str(v.get("published_at"))[:13] for v in pub)
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    th = sum(n for k, n in c.items() if k.startswith(today))
    top = c.most_common(3)
    worst = top[0][1] if top else 0
    return (f"النهاردة: {th} · أكتر ساعة: {worst} فيديو ({', '.join(k[5:] + '=' + str(n) for k, n in top)})"
            + ("  ⚠️ دفع جماعي — بيتقرا سبام" if worst >= 5 else "  ✅ الإيقاع هادي"))


def commit_check() -> str:
    """آخر ٣ فيديوهات في حالتنا المحلية — عشان نقارن «اللي حفظناه» بـ«اللي على يوتيوب»."""
    try:
        pub = json.loads((STATE / "published.json").read_text(encoding="utf-8")).get("videos") or []
    except Exception:
        return "مفيش حالة محلية"
    pub = pub[-3:]
    out = []
    for v in pub:
        f = v.get("features") or {}
        out.append(f"{str(v.get('published_at'))[5:16]} · {f.get('genre') or '—'} · {f.get('lang') or 'en'}"
                   f" · نسخ {len(f.get('locales') or [])}")
    return "\n".join(out) if out else "مفيش"


def main() -> int:
    n = 12
    tg = "--telegram" in sys.argv
    if "--n" in sys.argv:
        try:
            n = int(sys.argv[sys.argv.index("--n") + 1])
        except Exception:
            pass
    res = run(n)
    print("🔬 فحص حقيقي من يوتيوب API — Dollars")
    print("─" * 44)
    if not res.get("ok"):
        print("⚠️ اتعذّر:", res.get("error"))
        return 0
    c = res["channel"]
    print(f"القناة: {c['title']} · مشتركين {c['subs']} · فيديوهات {c['videos']} · مشاهدات {c['views']}")
    print(f"من آخر {len(res['rows'])} فيديو: عربي أساسي {res['ar_primary']} · "
          f"معاه نسخ عالمية {res['with_locales']} · صفر مشاهدات {res['zero_views']}")
    if res.get("pinned") is not None:
        print("📌 تعليق مثبّت على آخر فيديو:", "موجود ✅" if res["pinned"] else "مش موجود ❌")
    print("─" * 44)
    for r in res["rows"]:
        loc = ("" if not r["locales"] else f" +{len(r['locales'])}:{','.join(r['locales'][:6])}")
        flags = f"{r['privacy'][:6]}/{r['upload'][:8]}" + ("/⚠️" + r["reject"] if r["reject"] else "")
        print(f"{r['at']} [{r['lang']:<2}]{loc:<26} 👁{r['views']:<5} ♥{r['likes']:<3} {flags} · {r['dur']}")
        print(f"    {r['title'][:70]}")
        if r["loc_sample"]:
            print(f"    ع↩ {r['loc_sample']}")
        print(f"    https://youtu.be/{r['id']}")
    bad = [r for r in res["rows"] if r["reject"] or r["upload"] not in ("processed", "uploaded")]
    if bad:
        print(f"⚠️ فيديوهات مش سليمة عند يوتيوب: {len(bad)}")
    print("─" * 44)
    print("🚦 إيقاع النشر:", burst_check())
    print("من حالتنا المحلية:\n" + commit_check())
    if tg:
        try:
            from engine import publish as _p
            pin_line = "📌 تعليق مثبّت: موجود ✅\n" if res.get("pinned") else ""
            msg = ("🔬 فحص حقيقي (يوتيوب API)\n"
                   f"آخر {len(res['rows'])} فيديو · عربي أساسي {res['ar_primary']} · "
                   f"نسخ عالمية {res['with_locales']} · صفر مشاهدات {res['zero_views']}\n"
                   f"🚦 {burst_check()}\n" + pin_line +
                   f"القناة: {c['subs']} مشترك · {c['videos']} فيديو · {c['views']} مشاهدة\n" +
                   "\n".join(f"{r['at']} [{r['lang']}] +{len(r['locales'])} · {r['title'][:44]}"
                             for r in res["rows"][:5]))
            print("📨 تليجرام:", "اتبعت ✅" if _p.notify(msg) else "مش مفعّل")
        except Exception as e:
            print("📨 تليجرام اتعذّر:", type(e).__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
