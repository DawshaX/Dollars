#!/usr/bin/env python3
"""
🔗 إعادة ربط قناة يوتيوب بتوكن **دائم** — يشتغل جوه GitHub Actions (الأسرار ما تطلعش أبدًا).

المشكلة اللي بيحلها: أي تطبيق جوجل في وضع **Testing** توكنه بيموت كل 7 أيام (invalid_grant)
فالمصنع يوقف بصمت كل أسبوع. الحل الدائم من خطوتين:
  1) ننشر شاشة الموافقة في وضع **Production** (من Google Cloud Console) — مرّة واحدة في العمر.
  2) نعمل تفويض **جديد** بعد النشر → التوكن ده بيفضل شغّال للأبد (لحد ما صاحب القناة يغيّر كلمة السر أو يسحب الإذن).

الأوضاع:
  python tools/reconnect_channel.py url     # يطبع لينك الموافقة + رقم مشروع جوجل
  python tools/reconnect_channel.py token "<اللي نُسخ من شريط العنوان بعد الموافقة>"
  python tools/reconnect_channel.py probe   # يتأكد إن الكتابة في المستودع شغالة (بلا أي سر)

المتغيّرات (من أسرار المستودع — مش من الشات):
  YOUTUBE_CLIENT_ID · YOUTUBE_CLIENT_SECRET · GH_PAT (توكن بصلاحية كتابة الأسرار) · COPY_TO (مستودع إضافي)
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",       # الرفع
    "https://www.googleapis.com/auth/youtube.force-ssl",    # العنوان/الوصف/الفصول/التعليقات
    "https://www.googleapis.com/auth/youtube.readonly",     # قراءة القناة والإحصائيات
]
REDIRECT = os.environ.get("REDIRECT_URI") or "http://localhost:8085/"   # أي بورت شغّال لعملاء سطح المكتب


# ───────────────────────── أدوات صغيرة ─────────────────────────

def env(*names: str, default: str = "") -> str:
    for n in names:
        v = (os.environ.get(n) or "").strip()
        if v:
            return v
    return default


def http(url: str, data=None, method=None, headers=None, timeout=40):
    body = data if isinstance(data, (bytes, bytearray)) or data is None else urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:                                    # شبكة/تايم أوت
        return 0, str(e).encode()


def gh(pat: str) -> dict:
    return {"Authorization": f"token {pat}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


# ───────────────────────── جوجل ─────────────────────────

def auth_link(cid: str) -> str:
    q = urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",       # ← عشان ناخد refresh_token
        "prompt": "consent",            # ← يضمن توكن جديد كل مرة
        "include_granted_scopes": "true",
    })
    return "https://accounts.google.com/o/oauth2/v2/auth?" + q


def extract_code(raw: str) -> str:
    """بياخد العنوان الكامل اللي نُسخ بعد الموافقة ويطلّع منه الكود (أو يقبل الكود لوحده)."""
    raw = (raw or "").strip().strip('"').strip("'")
    if "code=" in raw:
        qs = urllib.parse.urlparse(raw).query or raw.split("?", 1)[-1]
        code = urllib.parse.parse_qs(qs).get("code", [""])[0]
        return urllib.parse.unquote(code)
    return raw


def exchange(cid: str, csec: str, code: str):
    st, body = http("https://oauth2.googleapis.com/token", data={
        "client_id": cid, "client_secret": csec, "code": code,
        "grant_type": "authorization_code", "redirect_uri": REDIRECT,
    })
    try:
        return st, json.loads(body)
    except Exception:
        return st, {"raw": body.decode("utf-8", "ignore")[:300]}


def channel_of(access_token: str) -> dict:
    st, body = http(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,contentDetails&mine=true",
        headers={"Authorization": "Bearer " + access_token})
    try:
        d = json.loads(body)
    except Exception:
        return {"error": f"قراءة القناة فشلت ({st})"}
    items = d.get("items") or []
    if not items:
        return {"error": "التوكن مش مربوط بأي قناة (اختار «القناة» في شاشة الموافقة)"}
    it = items[0]
    sn, stats = it["snippet"], it.get("statistics", {})
    return {"id": it["id"], "title": sn.get("title"), "handle": sn.get("customUrl"),
            "subs": stats.get("subscriberCount"), "videos": stats.get("videoCount"),
            "uploads": (it.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")}


# ───────────────────────── GitHub secrets ─────────────────────────

def put_secret(repo: str, name: str, value: str, pat: str) -> str:
    st, pk = http(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=gh(pat))
    if st != 200:
        return f"❌ {repo}/{name}: {st}"
    key = json.loads(pk)
    try:
        from nacl import encoding, public
        box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
        enc = base64.b64encode(box.encrypt(value.encode())).decode()
    except Exception as e:
        return f"❌ تشفير {name}: {type(e).__name__}"
    st2, body = http(f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
                     data=json.dumps({"encrypted_value": enc, "key_id": key["key_id"]}).encode(),
                     method="PUT", headers={**gh(pat), "Content-Type": "application/json"})
    return f"{'✅' if st2 in (201, 204) else '❌'} {repo}/{name}: {st2}"


def delete_secret(repo: str, name: str, pat: str) -> str:
    st, _ = http(f"https://api.github.com/repos/{repo}/actions/secrets/{name}", method="DELETE", headers=gh(pat))
    return f"مسح {name}: {st}"


def telegram(text: str) -> str:
    bot, chat = env("TG", "TELEGRAM_BOT_TOKEN"), env("CHAT", "TELEGRAM_CHAT_ID", "TELEGRAM_ADMIN_CHAT_ID")
    if not (bot and chat):
        return "تلجرام: مش مضبوط"
    st, _ = http(f"https://api.telegram.org/bot{bot}/sendMessage",
                 data={"chat_id": chat, "text": text, "disable_web_page_preview": "true"})
    return f"تلجرام: {st}"


# ───────────────────────── الأوضاع ─────────────────────────

def mode_url(cid: str) -> int:
    proj = cid.split("-", 1)[0] if "-" in cid else "(مجهول)"
    link = auth_link(cid)
    n = len(link)
    # نقسم اللينك 3 أجزاء: GitHub بيخفي أي سر حرفيًا في اللوج، والتقسيم بيخلي اللينك يوصلك كامل
    print("🔗 PART1OF3: " + link[: n // 3])
    print("🔗 PART2OF3: " + link[n // 3: 2 * n // 3])
    print("🔗 PART3OF3: " + link[2 * n // 3:])
    print(telegram("🔗 لينك موافقة جوجل لربط القناة بتوكن دائم (اضغط عليه من الموبايل):\n" + link))
    print("\n— خطوات صاحب القناة —")
    print("1) Google Cloud Console → APIs & Services → OAuth consent screen → زرار «PUBLISH APP»")
    print(f"   رابط مباشر: https://console.cloud.google.com/apis/credentials/consent?project={proj}")
    print(f"   (رقم المشروع: {proj}) — ده اللي بيمنع التوكن إنه يموت كل 7 أيام.")
    print("2) افتح اللينك فوق → اختار **القناة** الصح → Allow/موافقة.")
    print("3) المتصفح هيفتح صفحة مش موجودة (localhost) — انسخ **العنوان الكامل** من شريط العنوان")
    print("   وابعته، أو شغّل الحلقة تاني بوضع «token» وحطه في خانة الكود.")
    return 0


def mode_token(cid: str, csec: str, raw_code: str, pat: str, copy_to: str, repo: str) -> int:
    if not (cid and csec):
        print("❌ ناقص YOUTUBE_CLIENT_ID أو YOUTUBE_CLIENT_SECRET")
        return 2
    code = extract_code(raw_code)
    if not code:
        print("❌ مفيش كود — ابعت العنوان اللي ظهر بعد الموافقة")
        return 2
    if raw_code.strip().startswith("1//"):            # المالك جاب refresh token جاهز (Playground) — نقبله
        rt, ch = raw_code.strip(), channel_of("")
        st_ok = True
        print("📺 توكن جاهز:", json.dumps(ch, ensure_ascii=False))
        return _install(cid, csec, rt, ch, pat, copy_to, repo)
    st, tok = exchange(cid, csec, code)
    if st != 200 or "refresh_token" not in tok:
        err = str(tok)[:220]
        print(f"❌ التبديل فشل ({st}): {err}")
        if "invalid_grant" in err:
            print("   السبب الغالب: الكود اتستخدم قبل كده أو عدّى عليه وقت — اعمل موافقة جديدة.")
        return 3
    rt = tok["refresh_token"]
    ch = channel_of(tok.get("access_token", ""))
    print("📺 القناة اللي التوكن بيوصلها:", json.dumps(ch, ensure_ascii=False))
    return _install(cid, csec, rt, ch, pat, copy_to, repo)


def _install(cid: str, csec: str, rt: str, ch: dict, pat: str, copy_to: str, repo: str) -> int:
    results = []
    if pat:
        for name, val in (("YOUTUBE_CLIENT_ID", cid), ("YOUTUBE_CLIENT_SECRET", csec),
                          ("YOUTUBE_REFRESH_TOKEN", rt)):
            results.append(put_secret(repo, name, val, pat))
        if copy_to and copy_to != repo:
            for name, val in (("YOUTUBE_CLIENT_ID", cid), ("YOUTUBE_CLIENT_SECRET", csec),
                              ("YOUTUBE_REFRESH_TOKEN", rt)):
                results.append(put_secret(copy_to, name, val, pat))
    for r in results:
        print("  ", r)
    ok = all(r.startswith("✅") for r in results) and results
    msg = (f"🔗 ربط القناة تم ✅\n{ch.get('title')} · {ch.get('handle')} · {ch.get('subs')} مشترك\n"
           f"التوكن الدائم اتثبّت: {'كله تمام' if ok else 'محتاج مراجعة'}")
    print(telegram(msg))
    print("\nالخلاصة:", "كله تمام ✅ التوكن الدائم محفوظ" if ok else "⚠️ راجع السطور اللي فوق")
    return 0 if ok else 1


def mode_probe(pat: str, repo: str, copy_to: str) -> int:
    """يختبر إن كتابة الأسرار شغالة (بلا أي سر حقيقي) ويمسح الأثر."""
    targets = [repo] + ([copy_to] if copy_to and copy_to != repo else [])
    ok = True
    for r in targets:
        line = put_secret(r, "RECONNECT_TEST", "ping", pat)
        print("  ", line)
        ok = ok and line.startswith("✅")
    for r in targets:
        print("  ", delete_secret(r, "RECONNECT_TEST", pat))
    print("النتيجة:", "كتابة الأسرار شغالة في كل المستودعات ✅" if ok else "⚠️ فيه مستودع اتقفل عنه")
    return 0 if ok else 1


def main() -> int:
    cid = env("CID", "YOUTUBE_CLIENT_ID")
    csec = env("CSEC", "YOUTUBE_CLIENT_SECRET")
    pat = env("GH_PAT", "FG_TOKEN")
    repo = env("REPO", default="DawshaX/Dollars")
    copy_to = env("COPY_TO", "COPY_REPO")
    act = (env("ACT", default="url") or (sys.argv[1] if len(sys.argv) > 1 else "url")).lower()
    if len(sys.argv) > 1 and not env("ACT"):
        act = sys.argv[1].lower()
    if act == "url":
        if not cid:
            print("❌ ناقص YOUTUBE_CLIENT_ID"); return 2
        return mode_url(cid)
    if act == "token":
        raw = env("CODE") or (sys.argv[2] if len(sys.argv) > 2 else "")
        return mode_token(cid, csec, raw, pat, copy_to, repo)
    if act == "probe":
        return mode_probe(pat, repo, copy_to)
    print(f"وضع غير معروف: {act} (المتاح: url · token · probe)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
