#!/usr/bin/env python3
"""
🔗 مشاركة اعتماد يوتيوب بين المستودعات (مشروع جوجل كامل بحصته).

كل مشروع جوجل عنده ١٠٠٠٠ وحدة/يوم = ~٦ رفعات. لمّا نشغّل نفس القناة بمشاريع
مختلفة، السقف اليومي بيتضاعف — من غير ما نعمل حاجة يدوي.

الأمان أول حاجة: **مش بننسخ أي اعتماد غير لما نتأكد إنه لنفس قناتنا** (بنتحقق
منها من عند جوجل نفسه: channels.list?mine=true).

البيئة المطلوبة:
    CID / CSEC / RT       = اعتماد المشروع (السرّي)
    TARGET                = DawshaX/Dollars
    PREFIX                = 2 أو 3 (رقم المشروع في Dollars)
    EXPECT_CHANNEL        = UCG9g_26H65D3FahqyiYPHAw
    CROSS_PAT             = توكن GitHub بصلاحية كتابة الأسرار
"""
from __future__ import annotations

import base64
import json
import os
import urllib.parse
import urllib.request


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def post_form(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def api_get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def access_token(cid: str, csec: str, rt: str) -> str:
    out = post_form("https://oauth2.googleapis.com/token", {
        "client_id": cid, "client_secret": csec, "refresh_token": rt,
        "grant_type": "refresh_token"})
    return out["access_token"]


def my_channel(token: str) -> dict:
    d = api_get("https://www.googleapis.com/youtube/v3/channels?part=snippet,id&mine=true", token)
    it = (d.get("items") or [{}])[0]
    return {"id": it.get("id", ""), "title": (it.get("snippet") or {}).get("title", "")}


def put_secret(repo: str, name: str, value: str, pat: str) -> int:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers={"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        pk = json.load(r)
    from nacl import encoding, public
    sealed = base64.b64encode(
        public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder))
        .encrypt(value.encode())).decode()
    body = json.dumps({"encrypted_value": sealed, "key_id": pk["key_id"]}).encode()
    rq = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/secrets/{name}", data=body, method="PUT",
        headers={"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(rq, timeout=30) as r:
        return r.status


def main() -> int:
    cid, csec, rt = env("CID"), env("CSEC"), env("RT")
    target, prefix, want = env("TARGET"), env("PREFIX"), env("EXPECT_CHANNEL")
    pat = env("CROSS_PAT")
    if not (cid and csec and rt):
        print("⏭️ مفيش اعتماد كامل في المشروع ده — مفيش حاجة تتنقل.")
        return 0
    print(f"🔎 بنتأكد إن الاعتماد ده بتاع قناتنا ({want})…")
    try:
        tok = access_token(cid, csec, rt)
        ch = my_channel(tok)
    except Exception as e:
        print(f"⚠️ الاعتماد ده مش شغال ({type(e).__name__}: {str(e)[:150]}) — مش هننسخ حاجة.")
        return 0
    print(f"   القناة اللي بيرجعها جوجل: {ch['title']} · {ch['id']}")
    if ch["id"] != want:
        print("🚫 دي مش قناتنا — مش هننسخ حاجة (حماية من النشر على قناة غلط).")
        return 0
    if not pat:
        print("⚠️ مفيش CROSS_PAT — مش قادر أكتب في المستودع التاني.")
        return 1
    suf = "" if prefix == "1" else f"_{prefix}"
    for name, val in ((f"YOUTUBE_CLIENT_ID{suf}", cid), (f"YOUTUBE_CLIENT_SECRET{suf}", csec),
                      (f"YOUTUBE_REFRESH_TOKEN{suf}", rt)):
        code = put_secret(target, name, val, pat)
        print(f"   ✅ {target} ← {name} ({code})")
    print(f"🎉 مشروع جوجل رقم {prefix} بقى مضبوط في {target} — السقف اليومي زاد ٦ رفعات.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
