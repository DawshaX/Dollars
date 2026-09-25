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


def creds() -> dict:
    return {
        "client_id": _env("YOUTUBE_CLIENT_ID", "YT_CLIENT_ID"),
        "client_secret": _env("YOUTUBE_CLIENT_SECRET", "YT_CLIENT_SECRET"),
        "refresh_token": _env("YOUTUBE_REFRESH_TOKEN", "YT_REFRESH_TOKEN"),
    }


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
        "defaultAudioLanguage": "zxx",          # مفيش كلام — فهم بالصورة
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
    """رفع متقطّع (resumable) — لو النت قطع بيكمّل من مكانه."""
    video_path = pathlib.Path(video_path)
    size = video_path.stat().st_size
    body = {"snippet": _snippet(md), "status": _status(md)}
    if md.get("playlist"):
        body["snippet"]["title"] = body["snippet"]["title"][:100]
    token = token or access_token()
    init = urllib.request.Request(
        f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"},
        method="POST")
    with urllib.request.urlopen(init, timeout=60) as r:
        session = r.headers["Location"]
    with open(video_path, "rb") as fh:
        sent = 0
        while sent < size:
            data = fh.read(chunk)
            req = urllib.request.Request(
                session, data=data, method="PUT",
                headers={"Content-Length": str(len(data)),
                         "Content-Range": f"bytes {sent}-{sent + len(data) - 1}/{size}"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r2:
                    result = json.load(r2)
                    vid = result["id"]
                    return {"id": vid, "url": f"https://youtu.be/{vid}", "bytes": size}
            except urllib.error.HTTPError as e:
                if e.code in (500, 502, 503, 504):        # خطأ مؤقت ⇒ نعيد نفس الشريحة
                    time.sleep(3)
                    fh.seek(sent)
                    continue
                raise
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
    """كل حاجة مرة واحدة: رفع + غلاف + بلايليست + إشعار."""
    if not available()["ok"]:
        raise PublishUnavailable(available()["reason"])
    tok = access_token()
    res = upload(video_path, md, token=tok)
    if thumb_path:
        res["thumbnail"] = set_thumbnail(res["id"], thumb_path, token=tok)
    if md.get("playlist"):
        res["playlist"] = add_to_playlist(res["id"], md["playlist"], token=tok)
    notify(f"🎬 Dollars · نُشر: {md['titles'][0]}\n{res['url']}")
    return res
