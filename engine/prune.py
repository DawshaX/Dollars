"""
🧹 مكنسة القناة — تمسح الفيديوهات القديمة على دفعات (نظافة كاملة).
==================================================================
القديم = أي فيديو على القناة **قبل تاريخ البدء النضيف** (BEGIN) ومش من نشر المصنع الجديد.

- بتمشي على قائمة مرفوعات القناة (playlistItems) وتمسح (videos.delete = ٥٠ وحدة للفيديو).
- بتحترم الحصة: تسحب من المشاريع المخصّصة للمسح (role=prune) لحد ما تخلص وحدتها.
- بتسجّل كل خطوة في state/prune.json وبتبلّغ تليجرام (بداية · كل دفعة · خلاص).
- **مستحيل تمسح حاجة المصنع الجديد نشرها** (بتستثني state/published.json).

الاستخدام:
    from engine import prune
    prune.run(batch=120)        # يمسح لحد ١٢٠ فيديو قديم بحسب الحصة المتاحة
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

from engine import publish

STATE = pathlib.Path("state/prune.json")
BEGIN = "2026-09-26T00:00:00Z"          # كل ما قبل ده = قديم


def _load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"done": [], "skipped": [], "started": None}


def _save(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def _keep_ids() -> set:
    """الفيديوهات اللي المصنع الجديد نشرها — ممنوع تتلمس."""
    try:
        vids = json.loads(pathlib.Path("state/published.json").read_text(encoding="utf-8"))
        return {v.get("video_id") for v in vids.get("videos", []) if v.get("video_id")}
    except Exception:
        return set()


def list_old(token: str, channel_id: str, page: int = 50, max_pages: int = 20) -> list[dict]:
    """مرفوعات القناة الأقدم من تاريخ البدء (من غير فيديوهات المصنع الجديد)."""
    keep = _keep_ids()
    out, page_token = [], ""
    uploads = "UU" + channel_id[2:]
    for _ in range(max_pages):
        url = (f"{publish.API}/playlistItems?part=snippet,contentDetails&maxResults={page}"
               f"&playlistId={uploads}" + (f"&pageToken={page_token}" if page_token else ""))
        req = publish.urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with publish.urllib.request.urlopen(req, timeout=60) as r:
            d = json.load(r)
        for it in d.get("items", []):
            vid = (it.get("contentDetails") or {}).get("videoId")
            sn = it.get("snippet") or {}
            when = (sn.get("publishedAt") or "")
            if vid and vid not in keep and when < BEGIN:
                out.append({"id": vid, "title": (sn.get("title") or "")[:80], "at": when})
        page_token = d.get("nextPageToken") or ""
        if not page_token:
            break
    return out


def run(batch: int = 120, dry: bool = False, notify: bool = True) -> dict:
    """يمسح لحد batch فيديو قديم — **مقفول تمامًا** لحد ما صاحب القناة يوافق بنفسه.

    🔒 القفل: مفيش مسح أبدًا من غير PRUNE_APPROVED=1 (موافقة صريحة). ده حماية مطلقة
    بعد الطلب الواضح: «متتعملش حاجة من غير ما تسأل».
    """
    import os as _os
    if _os.environ.get("PRUNE_APPROVED") != "1":
        return {"ok": False, "locked": True, "deleted": 0,
                "reason": "🔒 المسح مقفول — محتاج موافقة صريحة من صاحب القناة (PRUNE_APPROVED=1)"}

    projs = publish.prune_projects()
    if not projs:
        return {"ok": False, "reason": "مفيش مشروع متاح للمسح"}

    budget = {c["project"]: publish.units_left(c["project"]) // publish.DELETE_UNITS for c in projs}
    total_budget = sum(budget.values())
    if total_budget <= 0:
        if notify:
            publish.notify("⛔ مكنسة القناة مستنية الحصة (مفيش وحدات متاحة للمسح النهاردة).")
        return {"ok": True, "deleted": 0, "reason": "quota", "budget": budget}

    st = _load()
    st.setdefault("done", [])
    st["started"] = st.get("started") or datetime.now(timezone.utc).isoformat()

    head = projs[0]
    tok = publish.access_token(head)
    ch = publish.my_channel(tok)
    if not ch.get("id"):
        return {"ok": False, "reason": "مش قادر أقرا القناة"}
    olds = list_old(tok, ch["id"])
    todo = [v for v in olds if v["id"] not in set(st["done"])][:min(batch, total_budget)]

    if notify:
        publish.notify(f"🧹 بدأ مسح القديم على «{ch.get('title')}»\n"
                       f"قديم متبقّي: {len(olds)} · هيمسح دلوقتي: {len(todo)}\n"
                       f"حصة المسح النهاردة: {total_budget} فيديو")

    deleted, failed = [], []
    for v in todo:
        proj = next((p for p in sorted(budget, key=lambda k: -budget[k]) if budget[p] > 0), None)
        if proj is None:
            break
        try:
            t = publish.access_token(publish.creds(proj))
            publish.delete_video(v["id"], t)
            publish.mark_units(proj, publish.DELETE_UNITS)
            budget[proj] -= 1
            deleted.append(v)
            st["done"].append(v["id"])
        except Exception as e:
            failed.append({"id": v["id"], "error": f"{type(e).__name__}: {str(e)[:150]}"})
    st["last_run"] = datetime.now(timezone.utc).isoformat()
    st["deleted_total"] = len(st["done"])
    _save(st)

    if notify and deleted:
        left = len(list_old(tok, ch["id"]))
        publish.notify(f"🧹 مسحنا {len(deleted)} فيديو قديم (إجمالي {st['deleted_total']}).\n"
                       f"فاضل على القناة: {left} قديم\n"
                       + (f"⚠️ فشل {len(failed)}: {failed[0]['error']}" if failed else "كله تمام ✅"))
    return {"ok": True, "deleted": len(deleted), "failed": failed,
            "remaining_old": max(0, len(olds) - len(deleted)), "budget": budget}


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    print(json.dumps(run(batch=n), ensure_ascii=False, indent=2))
