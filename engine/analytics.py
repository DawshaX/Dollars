"""
📊 الوكيل المراقب — Dollars Studio
==================================
بيقرأ أرقام الفيديوهات الحقيقية من يوتيوب (مشاهدات · لايكات · تعليقات) ويسلّمها للعقل
عشان **يطوّر نفسه** على النتائج الفعلية، مش على تخمين.

    python engine/analytics.py --sync      # يجيب الأرقام ويكتب state/analytics.json
    python engine/analytics.py --report    # تقرير: أحسن/أضعف الأنواع

بيحتاج مفتاح `YOUTUBE_API_KEY` (قراءة عامة — مش محتاج تسجيل دخول).
لو مفيش مفتاح: بيقول السبب ويخرج بنجاح (المصنع مايتوقفش).
"""
from __future__ import annotations

import json
import os
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
API = "https://www.googleapis.com/youtube/v3/videos"
CHANNEL_API = "https://www.googleapis.com/youtube/v3/channels"


def _jload(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _jdump(p, obj) -> pathlib.Path:
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def key() -> str | None:
    return os.environ.get("YOUTUBE_API_KEY") or os.environ.get("YT_API_KEY")


def _get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "DollarsStudio/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_stats(ids: list[str], api_key: str | None = None) -> dict:
    """مشاهدات/لايكات/تعليقات لأي عدد فيديوهات (حتى 50 في الطلب)."""
    api_key = api_key or key()
    if not api_key:
        raise RuntimeError("مفيش YOUTUBE_API_KEY")
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        chunk = [i for i in ids[i:i + 50] if i]
        if not chunk:
            continue
        q = urllib.parse.urlencode({"part": "statistics,snippet", "id": ",".join(chunk), "key": api_key})
        d = _get(f"{API}?{q}")
        for item in d.get("items", []):
            st = item.get("statistics", {})
            out[item["id"]] = {
                "title": (item.get("snippet") or {}).get("title"),
                "views": int(st.get("viewCount", 0) or 0),
                "likes": int(st.get("likeCount", 0) or 0),
                "comments": int(st.get("commentCount", 0) or 0),
            }
    return out


def channel_totals(api_key: str | None = None, handle: str = "@DollarsStudio") -> dict:
    """أرقام القناة نفسها (مشتركين · مشاهدات · عدد فيديوهات) — للمتابعة اليومية."""
    api_key = api_key or key()
    if not api_key:
        return {}
    for param in (("forHandle", handle), ("forUsername", handle.lstrip("@")), ("mine", "true")):
        try:
            q = urllib.parse.urlencode({"part": "statistics,snippet", **dict([param]), "key": api_key})
            d = _get(f"{CHANNEL_API}?{q}")
            if d.get("items"):
                st = d["items"][0].get("statistics", {})
                return {"title": d["items"][0]["snippet"]["title"],
                        "subs": int(st.get("subscriberCount", 0) or 0),
                        "views": int(st.get("viewCount", 0) or 0),
                        "videos": int(st.get("videoCount", 0) or 0)}
        except Exception:
            continue
    return {}


def sync(limit: int = 50, write: bool = True) -> dict:
    """يجيب أرقام كل فيديو منشور → state/analytics.json بالشكل اللي العقل بيفهمه."""
    published = (_jload(STATE / "published.json", {}) or {}).get("videos", [])
    if not published:
        return {"ok": False, "reason": "لسه مفيش فيديوهات منشورة — أول نشر وبعدين نبدأ نقيس"}
    if not key():
        return {"ok": False, "reason": "ناقص YOUTUBE_API_KEY (قراءة أرقام يوتيوب)"}
    ids = [v.get("video_id") for v in published[-limit:] if v.get("video_id")]
    stats = fetch_stats(ids)
    rows, gained, misses = [], 0, 0
    for v in published[-limit:]:
        s = stats.get(v.get("video_id"))
        if not s:
            misses += 1
            continue
        prev = int(v.get("views") or 0)
        gained += max(0, s["views"] - prev)
        rows.append({"title": s.get("title") or v.get("title"), "views": s["views"], "likes": s["likes"],
                     "comments": s["comments"], "features": v.get("features") or {},
                     "video_id": v.get("video_id"), "published_at": v.get("published_at")})
        v.update({"views": s["views"], "likes": s["likes"], "comments": s["comments"],
                  "last_checked": datetime.now(timezone.utc).isoformat()})
    ch = channel_totals()
    if write:
        _jdump(STATE / "published.json", {"videos": published})
        _jdump(STATE / "analytics.json", {"videos": rows, "channel": ch,
                                          "synced_at": datetime.now(timezone.utc).isoformat(),
                                          "views_gained": gained})
    return {"ok": True, "videos": len(rows), "misses": misses, "views_gained": gained, "channel": ch}


def report(path=None) -> str:
    d = _jload(path or (STATE / "analytics.json"), {}) or {}
    rows = d.get("videos") or []
    if not rows:
        return "📊 مفيش أرقام لسه — أول ما ننشر، التقرير ده هيبقى فيه مشاهدات حقيقية."
    rows = sorted(rows, key=lambda r: r.get("views", 0), reverse=True)
    ch = d.get("channel") or {}
    lines = [f"# 📊 تقرير أرقام القناة — {str(d.get('synced_at'))[:16]}", ""]
    if ch:
        lines.append(f"- القناة: **{ch.get('title', '—')}** · مشتركين {ch.get('subs', 0):,} · "
                     f"مشاهدات {ch.get('views', 0):,} · فيديوهات {ch.get('videos', 0):,}")
        lines.append("")
    lines.append("| الفيديو | مشاهدات | لايكات | تعليقات | النوع | الطول |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows[:20]:
        f = r.get("features") or {}
        lines.append(f"| {str(r.get('title'))[:52]} | {r.get('views', 0):,} | {r.get('likes', 0):,} | "
                     f"{r.get('comments', 0):,} | {f.get('pillar', '—')} | {f.get('duration_bucket', '—')} |")
    by = {}
    for r in rows:
        p = (r.get("features") or {}).get("pillar", "—")
        by.setdefault(p, []).append(r.get("views", 0))
    lines += ["", "## المتوسط حسب النوع"] + [f"- **{k}**: {sum(v)/len(v):,.0f} مشاهدات ({len(v)} فيديو)"
                                            for k, v in sorted(by.items(), key=lambda kv: -sum(kv[1])/len(kv[1]))]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="الوكيل المراقب — أرقام يوتيوب الحقيقية")
    ap.add_argument("--sync", action="store_true", help="يجيب الأرقام ويكتبها")
    ap.add_argument("--report", action="store_true", help="تقرير بالأرقام")
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()
    if a.sync:
        r = sync(limit=a.limit)
        print("✅ اتزامن:" if r.get("ok") else "ℹ️", r.get("reason") or
              f"{r['videos']} فيديو · +{r['views_gained']:,} مشاهدة جديدة · {r.get('channel') or ''}")
    if a.report or not a.sync:
        print(report())
