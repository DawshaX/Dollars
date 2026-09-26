"""
📤 النشر على يوتيوب — Dollars Studio
====================================
بيرفع الفيديو + الغلاف + البلايليست، وبيحطّ البيانات الكاملة (وصف · وسوم · إفصاح).
لو مفيش توكن للقناة: **مش بيفشل** — بيرجّع سبب واضح والمصنع بيكمّل ويحفظ الشغل في الطابور.

الأسرار المطلوبة (في إعدادات المستودع → Secrets):
    YOUTUBE_CLIENT_ID · YOUTUBE_CLIENT_SECRET · YOUTUBE_REFRESH_TOKEN
    (اختياري) TELEGRAM_BOT_TOKEN · TELEGRAM_CHAT_ID  → إشعار بكل نشر

الواجهة:
    from engine import publish
    publish.available()                    # → {"ok": bool, "reason": str}
    publish.upload("out/video.mp4", md)    # → {"id": ..., "url": ...}
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
import socket

socket.setdefaulttimeout(120)            # مفيش طلب يعلّق أكتر من دقيقتين

from datetime import datetime, timezone

try:                                     # البث الحي (اختياري — مايوقفش الشغل لو غاب)
    from engine import live as _live
except Exception:                        # pragma: no cover
    _live = None


def _say(text: str) -> None:
    if _live is not None:
        try:
            _live.say(text)
            return
        except Exception:
            pass
    print(text, flush=True)


def _jload(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def _jdump(path, obj) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"


class PublishUnavailable(RuntimeError):
    pass


def _env(*names: str) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v and v.strip():
            return v.strip()
    return None


def creds(project: int = 1) -> dict:
    """بيانات اعتماد مشروع جوجل رقم project (1 = الأساسي، 2/3/4 = مشاريع إضافية).

    كل مشروع جوجل عنده **حصة يومية مستقلة** (١٠٠٠٠ وحدة = ~٦ رفعات)،
    فكل مشروع إضافي بيزوّد سقف النشر اليومي — ودي طريقة «بلا حد» الحقيقية.
    """
    suf = "" if int(project) == 1 else f"_{int(project)}"
    return {
        "project": int(project),
        "client_id": _env(f"YOUTUBE_CLIENT_ID{suf}", f"YT_CLIENT_ID{suf}"),
        "client_secret": _env(f"YOUTUBE_CLIENT_SECRET{suf}", f"YT_CLIENT_SECRET{suf}"),
        "refresh_token": _env(f"YOUTUBE_REFRESH_TOKEN{suf}", f"YT_REFRESH_TOKEN{suf}"),
    }


def all_projects(max_projects: int = 4) -> list[dict]:
    """كل المشاريع المضبوطة عندنا (اللي عندها المفاتيح التلاتة كاملة)."""
    out = []
    for i in range(1, int(max_projects) + 1):
        c = creds(i)
        if all((c["client_id"], c["client_secret"], c["refresh_token"])):
            out.append(c)
    return out


PROJECTS_FILE = pathlib.Path("state/youtube_projects.json")
QUOTA_FILE = pathlib.Path("state/youtube_quota.json")
DAILY_UPLOADS_PER_PROJECT = 6      # ١٠٠٠٠ وحدة ÷ ١٦٠٠ = ٦ رفعات (قانون يوتيوب نفسه)


def my_channel(token: str) -> dict:
    """القناة اللي التوكن ده بيوصلها فعلاً (من عند جوجل نفسه)."""
    req = urllib.request.Request(f"{API}/channels?part=snippet,id&mine=true",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        it = ((json.load(r).get("items") or [{}]))[0]
    return {"id": it.get("id", ""), "title": ((it.get("snippet") or {}).get("title", ""))}


def usable_projects() -> list[dict]:
    """المشاريع المسموح النشر بيها: الأساسي + أي مشروع اتأكد إنه على **نفس القناة**.

    ملف state/youtube_projects.json بيتكتب من tools/verify_projects.py بعد ما يسأل جوجل.
    من غير الملف: بنشتغل بالمشروع الأساسي بس (أمان).
    """
    projs = all_projects()
    if not projs:
        return []
    try:
        rep = _jload(PROJECTS_FILE, {}) or {}
        usable = {str(x) for x in (rep.get("usable") or [])}
    except Exception:
        usable = set()
    out = [c for c in projs if c.get("project") == 1 or str(c.get("project")) in usable]
    return out


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def quota_state() -> dict:
    d = _jload(QUOTA_FILE, {}) or {}
    if d.get("date") != _today():                 # يوم جديد ⇒ عدّاد جديد
        d = {"date": _today(), "used": {}}
    d.setdefault("used", {})
    return d


def _quota_save(d: dict) -> None:
    try:
        _jdump(QUOTA_FILE, d)
    except Exception:
        pass


def quota_report() -> dict:
    """كام رفعة استُخدمت النهاردة لكل مشروع وكام فاضل."""
    st = quota_state()
    out = {}
    for c in usable_projects() or [creds(1)]:
        p = c.get("project", 1)
        used = int(st["used"].get(str(p), 0))
        out[str(p)] = {"used": used, "cap": DAILY_UPLOADS_PER_PROJECT,
                       "left": max(0, DAILY_UPLOADS_PER_PROJECT - used),
                       "ready": all((c["client_id"], c["client_secret"], c["refresh_token"]))}
    return {"date": st["date"], "projects": out}


def pick_project() -> dict | None:
    """يختار مشروع عنده حصة فاضلة النهاردة (التبادل بين المشاريع)."""
    st = quota_state()
    for c in usable_projects() or []:
        p = str(c.get("project", 1))
        if int(st["used"].get(p, 0)) < DAILY_UPLOADS_PER_PROJECT:
            return c
    return None


def remaining_capacity() -> int:
    """كام رفعة لسه ينفع ننزلها النهاردة (مجموع المشاريع المؤهلة)."""
    st = quota_state()
    cap = 0
    for c in usable_projects():
        p = str(c.get("project", 1))
        cap += max(0, DAILY_UPLOADS_PER_PROJECT - int(st["used"].get(p, 0)))
    return cap


def mark_upload(project: int, ok: bool = True) -> None:
    if not ok:
        return
    st = quota_state()
    p = str(int(project))
    st["used"][p] = int(st["used"].get(p, 0)) + 1
    _quota_save(st)


QUOTA_WORDS = ("quota", "exceeded", "rate limit", "ratelimit", "uploadlimitexceeded",
               "dailylimitexceeded", "too many requests", "403",
               "الحصة", "الكوتة", "كوتة")            # بالعربي كمان عشان مايضيّعش وقت رندر


def is_quota_error(err) -> bool:
    t = str(err).lower()
    return any(w in t for w in QUOTA_WORDS)


def _body(err) -> str:
    """نص رد يوتيوب (سبب الرفض الحقيقي) عشان نعرف نصلّح بدل التخمين."""
    try:
        raw = err.read()[:1200].decode("utf-8", "replace")
        d = json.loads(raw)
        e = (d.get("error") or {})
        reason = " · ".join(x.get("reason", "") for x in e.get("errors", []) or []) or e.get("status", "")
        msg = e.get("message", raw)
        return f"{reason} — {msg}"[:600]
    except Exception:
        return "(مفيش تفاصيل)"


def available(probe: bool = False) -> dict:
    c = creds()
    missing = [k for k, v in c.items() if not v]
    if missing:
        return {"ok": False, "reason": f"مفيش توكن للقناة (ناقص: {', '.join(missing)}) — الشغل هيتحفظ في الطابور",
                "missing": missing}
    if not probe:
        return {"ok": True, "reason": "التوكن موجود", "missing": []}
    try:
        access_token(c)
        return {"ok": True, "reason": "التوكن شغال ✅", "missing": []}
    except Exception as e:  # pragma: no cover - بيتوقف على الشبكة
        return {"ok": False, "reason": f"التوكن مش شغال: {type(e).__name__}: {e}", "missing": []}


def access_token(c: dict | None = None) -> str:
    c = c or creds()
    if not all(c.values()):
        raise PublishUnavailable("مفيش بيانات اعتماد للقناة")
    data = urllib.parse.urlencode({
        "client_id": c["client_id"], "client_secret": c["client_secret"],
        "refresh_token": c["refresh_token"], "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def _snippet(md: dict) -> dict:
    return {
        "title": md["titles"][0][:100],
        "description": md["description"][:4900],
        "tags": md.get("tags", [])[:35],
        "categoryId": str(md.get("category_id", "10")),
        "defaultLanguage": md.get("default_language", "en"),
        # ⚠️ ممنوع نبعت defaultAudioLanguage="zxx": يوتيوب بيرفض الرفع كله (INVALID_REQUEST_METADATA).
        # سيبناها فاضية = «مفيش لغة كلام» وهو ده الافتراضي الآمن للفيديوهات الصامتة.
    }


def _status(md: dict) -> dict:
    st = {
        "privacyStatus": md.get("upload_defaults", {}).get("visibility", "public"),
        "selfDeclaredMadeForKids": bool(md.get("made_for_kids", False)),
        "license": "youtube",
        "embeddable": True,
        "publicStatsViewable": True,
    }
    return st


def upload(video_path, md: dict, token: str | None = None, chunk: int = 8 * 1024 * 1024,
           timeout: int = 600) -> dict:
    """رفع بالبيانات اللي المصنع بيبنيها."""
    return put_video(video_path, {"snippet": _snippet(md), "status": _status(md)},
                     token=token, chunk=chunk, timeout=timeout)


def put_video(video_path, body: dict, token: str | None = None, chunk: int = 8 * 1024 * 1024,
              timeout: int = 600, extra_query: str = "&part=snippet,status",
              headers: dict | None = None) -> dict:
    """رفع متقطّع (resumable) بالبيانات الخام — لو النت قطع بيكمّل من مكانه.

    موحّد هنا عشان دكتور الرفع يجرّب بيانات مختلفة على **نفس الميكانيكا** بالظبط.
    """
    video_path = pathlib.Path(video_path)
    size = video_path.stat().st_size
    token = token or access_token()
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"}
    hdrs.update(headers or {})
    init = urllib.request.Request(
        f"{UPLOAD_URL}?uploadType=resumable{extra_query}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=hdrs, method="POST")
    _say(f"   ⬆️ بنبدأ جلسة الرفع على يوتيوب ({size/1024/1024:.1f} ميجا)…")
    try:
        with urllib.request.urlopen(init, timeout=60) as r:
            session = r.headers["Location"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"يوتيوب رفض بيانات الفيديو — HTTP {e.code}: {_body(e)}") from None
    with open(video_path, "rb") as fh:
        sent = 0
        retries = 0
        while sent < size:
            data = fh.read(chunk)
            req = urllib.request.Request(
                session, data=data, method="PUT",
                headers={"Content-Length": str(len(data)),
                         "Content-Range": f"bytes {sent}-{sent + len(data) - 1}/{size}"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r2:
                    if r2.status in (308, 204):           # شريحة وسطانية — لسه فيه باقي
                        sent += len(data)
                        continue
                    raw = r2.read()
                    if not raw.strip():                   # مفيش رد = لسه فيه باقي
                        _say(f"   ⏳ شريحة {sent//chunk + 1} وصلت — بنكمّل الباقي")
                        sent += len(data)
                        continue
                    result = json.loads(raw)
                    vid = result["id"]
                    _say(f"   ✅ يوتيوب استقبل الفيديو: {vid}")
                    return {"id": vid, "url": f"https://youtu.be/{vid}", "bytes": size}
            except urllib.error.HTTPError as e:
                if e.code in (500, 502, 503, 504):        # خطأ مؤقت ⇒ نعيد نفس الشريحة (بس مش للأبد)
                    retries += 1
                    if retries > 5:
                        raise RuntimeError(f"يوتيوب رافض يستقبل الملف ({e.code}) بعد ٥ محاولات") from None
                    _say(f"   🔁 الشريحة رجعت {e.code} — محاولة {retries}/5")
                    time.sleep(3)
                    fh.seek(sent)
                    continue
                if e.code in (308,):                      # شريحة اتقبلت، كمّل الباقي
                    sent += len(data)
                    continue
                raise RuntimeError(f"يوتيوب رفض الرفع — HTTP {e.code}: {_body(e)}") from None
            sent += len(data)
    raise RuntimeError("الرفع وقف قبل ما يكمّل")


def set_thumbnail(video_id: str, image_path, token: str | None = None) -> bool:
    token = token or access_token()
    img = pathlib.Path(image_path).read_bytes()
    req = urllib.request.Request(
        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
        data=img, headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status == 200
    except Exception:
        return False


def playlist_id(name: str, create: bool = True, token: str | None = None) -> str | None:
    token = token or access_token()
    hdr = {"Authorization": f"Bearer {token}"}
    q = urllib.parse.quote(name)
    try:
        with urllib.request.urlopen(urllib.request.Request(
                f"{API}/playlists?part=snippet&mine=true&maxResults=50", headers=hdr), timeout=30) as r:
            for it in json.load(r).get("items", []):
                if it["snippet"]["title"].strip().lower() == name.strip().lower():
                    return it["id"]
        if not create:
            return None
        body = json.dumps({"snippet": {"title": name}, "status": {"privacyStatus": "public"}}).encode()
        req = urllib.request.Request(f"{API}/playlists?part=snippet,status", data=body,
                                     headers={**hdr, "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)["id"]
    except Exception:
        return None


def add_to_playlist(video_id: str, playlist: str, token: str | None = None) -> bool:
    pid = playlist_id(playlist, token=token)
    if not pid:
        return False
    token = token or access_token()
    body = json.dumps({"snippet": {"playlistId": pid,
                                   "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).encode()
    req = urllib.request.Request(f"{API}/playlistItems?part=snippet", data=body,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def notify(text: str) -> bool:
    """إشعار تليجرام (اختياري) — لو المفاتيح موجودة."""
    tok, chat = _env("TELEGRAM_BOT_TOKEN"), _env("TELEGRAM_CHAT_ID", "TELEGRAM_ADMIN_CHAT_ID")
    if not (tok and chat):
        return False
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3900],
                                   "disable_web_page_preview": "true"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


def publish(video_path, md: dict, thumb_path=None) -> dict:
    """كل حاجة مرة واحدة: رفع + غلاف + بلايليست + إشعار — **بينوّع بين مشاريع جوجل**."""
    if not available()["ok"]:
        raise PublishUnavailable(available()["reason"])
    tried, last_err = [], None
    while True:
        c = pick_project()
        if c is None:
            raise PublishUnavailable(
                "quota: الحصة اليومية خلصت على كل مشاريع جوجل — الشغل هيتحفظ في الطابور "
                f"وينزل تلقائي أول ما الحصة ترجع. ({quota_report()['projects']})")
        try:
            tok = access_token(c)
            res = upload(video_path, md, token=tok)
            mark_upload(c.get("project", 1), True)
            res["project"] = c.get("project", 1)
            break
        except Exception as e:
            if is_quota_error(e):
                mark_upload(c.get("project", 1), True)       # نحسبها مستهلكة ونروح لمشروع تاني
                tried.append(c.get("project", 1))
                last_err = e
                continue
            raise
    if tried:
        md = dict(md or {})
        md["projects_tried"] = tried
    if thumb_path:
        res["thumbnail"] = set_thumbnail(res["id"], thumb_path, token=tok)
    if md.get("playlist"):
        res["playlist"] = add_to_playlist(res["id"], md["playlist"], token=tok)
    record(res, md)                       # نسجّل الفيديو (وبصمته) عشان العقل يتعلم من أرقامه بعدين
    notify(f"🎬 Dollars · نُشر: {md['titles'][0]}\n{res['url']}")
    return res


def record(res: dict, md: dict) -> pathlib.Path:
    """يحفظ كل فيديو اتنشر + بصمته (نوعه · الساعة · الطول) في state/published.json."""
    p = pathlib.Path("state/published.json")
    d = _jload(p, {"videos": []}) or {"videos": []}
    ts = md.get("slot") or {}
    d["videos"].append({
        "video_id": res.get("id"), "url": res.get("url"), "title": md["titles"][0],
        "published_at": datetime.now(timezone.utc).isoformat(),
        "features": {"pillar": md.get("pillar"), "kind": md.get("kind"), "kw": md.get("kw"),
                     "hour": ts.get("hour"), "duration_bucket": md.get("duration_bucket") or ts.get("kind")},
        "views": 0, "likes": 0, "comments": 0,
        "thumbnail": bool(md.get("thumbnail_texts")), "playlist": md.get("playlist"),
    })
    return _jdump(p, d)
