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
    vids = api("https://www.googleapis.com/youtube/v3/videos?part=snippet,localizations,statistics"
               f"&id={','.join(ids)}", token)
    rows = []
    for v in (vids.get("items") or []):
        s = v.get("snippet") or {}
        loc = v.get("localizations") or {}
        rows.append({"id": v.get("id"), "at": (s.get("publishedAt") or "")[:16],
                     "lang": s.get("defaultLanguage") or "—", "locales": sorted(loc.keys()),
                     "title": s.get("title") or "", "views": int((v.get("statistics") or {}).get("viewCount") or 0),
                     "likes": int((v.get("statistics") or {}).get("likeCount") or 0),
                     "comments": int((v.get("statistics") or {}).get("commentCount") or 0)})
    return {"ok": True, "channel": {"title": (it.get("snippet") or {}).get("title"),
                                    "subs": st.get("subscriberCount"), "videos": st.get("videoCount"),
                                    "views": st.get("viewCount")},
            "rows": rows,
            "ar_primary": sum(1 for r in rows if r["lang"].startswith("ar")),
            "with_locales": sum(1 for r in rows if r["locales"]),
            "zero_views": sum(1 for r in rows if r["views"] == 0)}


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
    print("─" * 44)
    for r in res["rows"]:
        loc = ("" if not r["locales"] else f" +{len(r['locales'])}:{','.join(r['locales'][:6])}")
        print(f"{r['at']} [{r['lang']:<2}]{loc:<28} 👁{r['views']:<5} ♥{r['likes']:<3} 💬{r['comments']:<2} "
              f"{r['title'][:52]}")
        print(f"    https://youtu.be/{r['id']}")
    print("─" * 44)
    print("من حالتنا المحلية:\n" + commit_check())
    if tg:
        try:
            from engine import publish as _p
            msg = ("🔬 فحص حقيقي (يوتيوب API)\n"
                   f"آخر {len(res['rows'])} فيديو · عربي أساسي {res['ar_primary']} · "
                   f"نسخ عالمية {res['with_locales']} · صفر مشاهدات {res['zero_views']}\n"
                   f"القناة: {c['subs']} مشترك · {c['videos']} فيديو · {c['views']} مشاهدة\n"
                   + "\n".join(f"{r['at']} [{r['lang']}] +{len(r['locales'])} · {r['title'][:44]}"
                               for r in res["rows"][:5]))
            print("📨 تليجرام:", "اتبعت ✅" if _p.notify(msg) else "مش مفعّل")
        except Exception as e:
            print("📨 تليجرام اتعذّر:", type(e).__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
