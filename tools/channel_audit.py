"""🔎 فحص القناة الكامل — Dollars Studio

يسحب **كل** فيديوهات القناة (مش اللي عندنا في السجل بس) بأرقامها الحقيقية ويحلّلها:

    python tools/channel_audit.py              # فحص + تقرير
    python tools/channel_audit.py --telegram   # ويبعت التقرير على تليجرام

بيطلع: عدد الفيديوهات · إجمالي المشاهدات · أعلى/أقل الفيديوهات · نسبة الفيديوهات بلا مشاهدات ·
توزيع المشاهدات على الأيام · أداء كل نوع/مجموعة (وصف · هاشتاج · مدة) — عشان العقل يتعلم من الحقيقي.
بيحتاج توكن القناة (نفس مفاتيح النشر) — مفيش مشروع جوجل جديد.
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path[:] = [q for q in sys.path if pathlib.Path(q or ".").resolve() != pathlib.Path(__file__).resolve().parent]
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import publish  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"
STATE = ROOT / "state"


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                               "User-Agent": "DollarsStudio/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _all_upload_ids(token: str, uploads: str, cap: int = 800) -> list[str]:
    ids, tok = [], None
    while len(ids) < cap:
        q = {"part": "contentDetails", "playlistId": uploads, "maxResults": "50"}
        if tok:
            q["pageToken"] = tok
        d = _get(f"{API}/playlistItems?{urllib.parse.urlencode(q)}", token)
        for it in d.get("items", []):
            vid = ((it.get("contentDetails") or {}).get("videoId"))
            if vid:
                ids.append(vid)
        tok = d.get("nextPageToken")
        if not tok:
            break
    return ids


def _videos(token: str, ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        q = urllib.parse.urlencode({"part": "snippet,statistics,contentDetails,status",
                                    "id": ",".join(chunk)})
        d = _get(f"{API}/videos?{q}", token)
        for it in d.get("items", []):
            sn, st, cd, stat = it.get("snippet") or {}, it.get("statistics") or {}, \
                it.get("contentDetails") or {}, it.get("status") or {}
            dur = cd.get("duration") or "PT0S"
            secs = 0
            try:
                import re
                m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
                secs = int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)
            except Exception:
                pass
            out.append({
                "id": it["id"], "title": sn.get("title"), "published": sn.get("publishedAt"),
                "category": sn.get("categoryId"), "tags": len(sn.get("tags") or []),
                "hashtags": len([w for w in (sn.get("description") or "").split() if w.startswith("#")]),
                "desc_len": len(sn.get("description") or ""), "seconds": secs,
                "views": int(stat.get("viewCount", 0) or 0), "likes": int(stat.get("likeCount", 0) or 0),
                "comments": int(stat.get("commentCount", 0) or 0),
                "privacy": st.get("privacyStatus"), "upload": st.get("uploadStatus"),
                "kids": st.get("madeForKids"),
            })
    return out


def audit(cap: int = 800) -> dict:
    tokens = []
    for prj in publish.all_projects():
        try:
            t = publish.access_token(prj)
            if t:
                tokens.append(t)
        except Exception:
            continue
    if not tokens:
        return {"ok": False, "reason": "مفيش توكن قناة (مفاتيح النشر)"}
    token = tokens[0]
    ch = _get(f"{API}/channels?part=snippet,statistics,contentDetails,brandingSettings&mine=true", token)
    item = (ch.get("items") or [{}])[0]
    sn, st = item.get("snippet") or {}, item.get("statistics") or {}
    brand = (item.get("brandingSettings") or {}).get("channel") or {}
    uploads = ((item.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    ids = _all_upload_ids(token, uploads, cap=cap) if uploads else []
    vids = _videos(token, ids)
    vids.sort(key=lambda v: v.get("published") or "")

    total = sum(v["views"] for v in vids)
    zeros = [v for v in vids if v["views"] == 0]
    per_day = defaultdict(lambda: {"n": 0, "views": 0})
    for v in vids:
        d = (v.get("published") or "")[:10]
        per_day[d]["n"] += 1
        per_day[d]["views"] += v["views"]
    dur_bucket = defaultdict(lambda: {"n": 0, "views": 0})
    for v in vids:
        s = v["seconds"]
        b = "short(<60)" if s < 61 else ("1-10د" if s < 600 else ("10-60د" if s < 3600 else "1س+"))
        dur_bucket[b]["n"] += 1
        dur_bucket[b]["views"] += v["views"]
    rep = {
        "ok": True, "at": datetime.now(timezone.utc).isoformat(),
        "channel": {"title": sn.get("title"), "id": item.get("id"), "subs": int(st.get("subscriberCount", 0) or 0),
                    "views_lifetime": int(st.get("viewCount", 0) or 0), "videos": int(st.get("videoCount", 0) or 0),
                    "country": brand.get("country"), "keywords": brand.get("keywords"),
                    "desc": (brand.get("description") or "")[:400],
                    "default_language": (brand.get("defaultLanguage") or None)},
        "scanned": len(vids), "views_scanned": total, "zero_views": len(zeros),
        "zero_pct": round(100.0 * len(zeros) / max(1, len(vids)), 1),
        "top": sorted(vids, key=lambda v: -v["views"])[:12],
        "bottom": sorted(vids, key=lambda v: v["views"])[:6],
        "by_day": {k: v for k, v in sorted(per_day.items())},
        "by_duration": dict(dur_bucket),
        "cat": Counter(v.get("category") for v in vids).most_common(6),
        "with_tags": sum(1 for v in vids if v["tags"]),
        "with_hashtags": sum(1 for v in vids if v["hashtags"]),
        "all": vids,
    }
    return rep


def report(r: dict) -> str:
    if not r.get("ok"):
        return "❌ فحص القناة: " + str(r.get("reason"))
    c = r["channel"]
    L = [f"🔎 فحص القناة — {c['title']}",
         f"👥 مشتركين {c['subs']:,} · 👁️ مشاهدات كلية {c['views_lifetime']:,} · 🎬 فيديوهات {c['videos']:,}",
         f"🌍 بلد القناة: {c.get('country') or 'مش محدّد'} · كلمات القناة: {'موجودة' if c.get('keywords') else '❌ مفقودة'}",
         f"📄 وصف القناة: {'موجود' if c.get('desc') else '❌ مفقود'} · اللغة الافتراضية: {c.get('default_language') or '❌ مش محددة'}",
         f"📦 فحصنا {r['scanned']} فيديو · مشاهداتهم {r['views_scanned']:,} · "
         f"بلا مشاهدات {r['zero_views']} ({r['zero_pct']}%)"]
    L.append("— توزيع المشاهدات على المدة —")
    for k, v in r["by_duration"].items():
        L.append(f"   {k}: {v['n']} فيديو · {v['views']:,} مشاهدة (متوسط {v['views']//max(1,v['n'])})")
    L.append("— أعلى ٨ —")
    for v in r["top"][:8]:
        L.append(f"   {v['views']:>7,} · {v['likes']}👍 · {str(v['title'])[:58]} · {v['seconds']}ث")
    L.append(f"— فيديوهات بعنوان فيه تاجات: {r['with_tags']}/{r['scanned']} · بهاشتاجات: {r['with_hashtags']}/{r['scanned']}")
    return "\n".join(L)


def main() -> int:
    r = audit()
    txt = report(r)
    print(txt)
    try:
        (STATE / "channel_audit.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        (STATE / "channel_audit.md").write_text(txt, encoding="utf-8")
        print("\n💾 اتكتب: state/channel_audit.json + .md")
    except Exception as e:
        print("⚠️ الحفظ فشل:", type(e).__name__)
    if "--telegram" in sys.argv:
        try:
            ok = publish.notify("📊 Dollars · فحص القناة الكامل\n\n" + txt[:3500])
            print("📨 تليجرام:", "اتبعت" if ok else "فشل")
        except Exception as e:
            print("📨 تليجرام: فشل —", type(e).__name__)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
