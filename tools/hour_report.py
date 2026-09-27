"""📈 تقرير الساعة — Dollars Studio

بيقرا الحالة الحقيقية (سجل النشر + التحليلات + الطابور + الحصة) ويبعت تقرير قصير على تليجرام:

    python tools/hour_report.py            # طباعة
    python tools/hour_report.py --telegram # وإرسال

بيجاوب على ٤ أسئلة: نزل كام في آخر ساعة؟ إجمالي النهاردة كام؟ فيه مشاهدات/تفاعل؟
الطابور والحصة أخبارهم إيه؟
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STATE = ROOT / "state"


def _j(name: str, default):
    p = STATE / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def build() -> str:
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(hours=1)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    pub = (_j("published.json", {}) or {}).get("videos", []) or []
    last_h, today = [], []
    for v in pub:
        try:
            ts = datetime.fromisoformat(str(v.get("published_at")).replace("Z", "+00:00"))
        except Exception:
            continue
        if ts >= hour_ago:
            last_h.append(v)
        if ts >= day_start:
            today.append(v)
    # 🔬 إثبات آخر فيديو (نسخ عالمية · لفّ · تعليق مثبّت)
    proof = ""
    if pub:
        _last = sorted(pub, key=lambda v: str(v.get("published_at") or ""))[-1]
        _f = _last.get("features") or {}
        proof = (f"🔬 آخر فيديو: {str(_last.get('title'))[:44]}\n"
                 f"   نسخ عالمية: {len(_f.get('locales') or [])} · "
                 f"لفّ: {'✓' if _f.get('loop') else '—'} · تعليق: {'✓' if _f.get('pinned') else '—'} · "
                 f"مشاهدات: {_last.get('views', 0)}\n   {( _last.get('url') or '')}\n")
    an = _j("analytics.json", {}) or {}
    rows = an.get("videos") or []
    views = sum(int(r.get("views") or 0) for r in rows)
    likes = sum(int(r.get("likes") or 0) for r in rows)
    comments = sum(int(r.get("comments") or 0) for r in rows)
    ch = an.get("channel") or {}
    q = (_j("queue.json", {}) or {}).get("items", []) or []
    audit = _j("channel_audit.json", {}) or {}
    deep = _j("analytics_deep.json", {}) or {}
    imp = ((deep.get("parts") or {}).get("impressions") or {})
    imp_txt = ""
    if imp.get("rows"):
        imp_txt = f" · 🚀 ظهور {imp['rows'][0][0]:,} · نقر {imp['rows'][0][1]:.1%}"
    elif imp.get("error"):
        imp_txt = " · 🚀 الظهور: محتاج تفعيل خدمة التحليلات"
    L = [f"📈 تقرير Dollars — {now.strftime('%H:%M')} UTC",
         f"⏱️ آخر ساعة: {len(last_h)} فيديو" + (f" (آخرهم: {str(last_h[-1].get('title'))[:40]})" if last_h else ""),
         f"📅 النهاردة: {len(today)} فيديو · إجمالي المنشور عندنا: {len(pub)}",
         f"👁️ مشاهدات المتقاسة: {views:,} · ❤️ {likes} · 💬 {comments}" + imp_txt,
         f"📺 القناة: {ch.get('subs', '؟')} مشترك · {ch.get('videos', '؟')} فيديو · "
         f"{ch.get('views', 0):,} مشاهدة كلية" if ch else "📺 القناة: مفيش أرقام لسه",
         f"📦 الطابور: {len(q)} عنصر مستني"]
    if audit.get("zero_pct") is not None:
        L.append(f"📉 فيديوهات بلا مشاهدات: {audit.get('zero_pct')}% من {audit.get('scanned')} فحصناها")
    if proof:
        L.append(proof.rstrip())
    return "\n".join(L)


def main() -> int:
    txt = build()
    print(txt)
    if "--telegram" in sys.argv:
        try:
            from engine import publish
            print("📨 تليجرام:", "اتبعت" if publish.notify(txt) else "فشل")
        except Exception as e:
            print("📨 فشل:", type(e).__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
