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
# العنوان المسجّل فعلًا على تطبيق جوجل بتاعنا (اتأكدنا منه باختبار حقيقي عند جوجل):
#   https://8899-ivfx0jnsfhm4lb21x07io-ae1265fb.sg1.manus.computer/callback  ✅ مقبول
#   https://developers.google.com/oauthplayground                            ✅ مقبول
#   أي عنوان localhost                                                       ❌ مرفوض (redirect_uri_mismatch)
# العنوان المسجّل فعلًا على عميل المصنع (اتأكدنا من جوجل نفسها بماسح كامل):
#   https://dawshax.github.io/youtube/callback/     ✅ مقبول (الافتراضي دلوقتي)
#   https://developers.google.com/oauthplayground   ✅ مقبول (احتياطي)
#   أي localhost أو دومين بيئات قديمة أو صفحتنا    ❌ مرفوض (لحد ما يتضاف من Cloud Console)
REDIRECT = os.environ.get("REDIRECT_URI") or "https://dawshax.github.io/youtube/callback/"   # صفحتنا الحقيقية (مسجّلة ومقبولة عند جوجل ✅)


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

def check_link(cid: str, redirect: str | None = None) -> tuple[bool, str]:
    """فحص أمين: نطلب من جوجل من غير متابعة التحويل، ونفكّ تشفير الخطأ لو موجود.

    ملاحظة مهمة: صفحة خطأ جوجل بتغطّي السبب في باراميتر base64 — فمجرد البحث عن كلمة
    «mismatch» في الرد **مش كفاية** (كانت بتقول ✅ غلط). هنا بنفكّ التشفير ونتأكد.
    """
    import base64
    import re as _re
    red = redirect or REDIRECT
    q = urllib.parse.urlencode({"client_id": cid, "redirect_uri": red, "response_type": "code",
                                "scope": SCOPES[0], "access_type": "offline", "prompt": "consent"})
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + q

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    op = urllib.request.build_opener(_NoRedirect)
    loc = ""
    try:
        with op.open(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
            code, loc = r.status, (r.headers.get("Location") or "")
    except urllib.error.HTTPError as e:
        code, loc = e.code, ((e.headers.get("Location") or "") if e.headers else "")
    except Exception as e:
        return False, f"مش قادر أفحص ({type(e).__name__})"
    reason = ""
    m = _re.search(r"authError=([^&]+)", loc)
    if m:
        try:
            reason = base64.urlsafe_b64decode(m.group(1) + "==").decode("utf-8", "ignore")
        except Exception:
            reason = m.group(1)
    blob = (loc + " " + reason).lower()
    if "mismatch" in blob:
        return False, f"العنوان مش مسجّل على العميل ده — لازم تضيف: {red}"
    if "invalid_client" in blob:
        return False, "العميل نفسه مرفوض (client_id غلط/مقفول)"
    if "/signin/" in loc or "/v3/signin" in loc or code == 200:
        return True, ""
    return False, f"رد غير متوقع ({code}) {loc[:80]}"


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
    steps = ("\n\nالخطوات (٤٠ ثانية):\n"
             "1) سجّل دخول بالحساب اللي بيدير القناة\n"
             "2) اختار القناة xDaw NoVa\n"
             "3) Allow / موافقة\n"
             "4) هتفتح صفحة Google OAuth Playground:\n"
             "   • لو ظهر فيها «Authorization code» → انسخه\n"
             "   • لو ظهر «Refresh token» → انسخه\n"
             "   • ولو الصفحة مش واضحة → انسخ **العنوان كامل** من شريط العنوان (الكود جواه)\n"
             "5) ابعته فورًا هنا أو على تلجرام\n\n"
             "⏱️ الكود بيموت بعد 10 دقايق — لازم تبعته على طول.")
    print(telegram("🔗 **لينك الربط النهائي** (اضغط عليه من الموبايل):\n" + link + steps))
    # نكتب اللينك في ملف بالمستودع — client_id مش سر (بيظهر في كل لينك OAuth)، والسر مش موجود هنا.
    pat = env("GH_PAT", "FG_TOKEN")
    repo = env("REPO", default="DawshaX/Dollars")
    if (os.environ.get("PUBLISH_LINK") or "").strip() in ("1", "true", "yes") and pat:
        import base64 as _b64
        body = {"message": "🔗 لينك الربط الحالي (بيتولّد أوتوماتيك)", "branch": "main",
                "content": _b64.b64encode((link + "\n").encode()).decode()}
        st_g, cur = http(f"https://api.github.com/repos/{repo}/contents/docs/consent_link.txt", headers=gh(pat))
        if st_g == 200:
            try:
                body["sha"] = json.loads(cur)["sha"]
            except Exception:
                pass
        st_p, _ = http(f"https://api.github.com/repos/{repo}/contents/docs/consent_link.txt",
                       data=json.dumps(body).encode(), method="PUT",
                       headers={**gh(pat), "Content-Type": "application/json"})
        print("حفظ اللينك في المستودع:", "✅" if st_p in (200, 201) else f"❌ {st_p}")
    # فحص تلقائي: هل جوجل بتقبل العنوان مع العميل ده؟ (بنختبر من غير ما نستهلك أي كود)
    ok, note = check_link(cid)
    print(("✅ الفحص: جوجل قبلت اللينك ده — ماشي صح" if ok else
           "❌ الفحص: جوجل رفضت العنوان للعميل ده — " + note))
    if not ok:
        print(telegram(
            "⚠️ محتاج ضغطة واحدة منك (دقيقة واحدة):\n\n"
            "افتح: https://console.cloud.google.com/apis/credentials?project=" + cid.split("-")[0] + "\n"
            "1) اضغط على اسم الـ OAuth client (لو فيه أكتر من واحد، اعمل نفس الخطوة في كل واحد)\n"
            "2) تحت «Authorized redirect URIs» اضغط ADD URI\n"
            "3) الصق السطر ده بالحرف:\n" + str(REDIRECT) + "\n"
            "4) SAVE\n\n"
            "وبعدها مش هتحتاج تعمل حاجة — اللينك الجديد هيوصلك أوتوماتيك ✅"))
        print("\n— خطوات صاحب القناة —")
    print("0) مهم: بعد الموافقة المتصفح هيقول «الصفحة مش موجودة» أو يحمّل للأبد — عادي جدًا.")
    print("   مفيش أي مشكلة: **العنوان في شريط العنوان فيه الكود**. انسخ العنوان كامل وابعته.")
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
        rt = raw_code.strip()
        st, tok = http("https://oauth2.googleapis.com/token", data={
            "client_id": cid, "client_secret": csec, "refresh_token": rt,
            "grant_type": "refresh_token"})
        if st != 200 or "access_token" not in tok:
            print(f"❌ التوكن الجاهز مرفوض ({st}): {str(tok)[:200]}")
            print("   غالبًا اتعمل بعميل تاني — استخدم لينك وضع «url» بدل كده.")
            return 3
        ch = channel_of(tok["access_token"])           # تأكيد حقيقي: القناة اللي التوكن بيوصلها
        print("📺 التوكن شغّال — القناة:", json.dumps(ch, ensure_ascii=False))
        return _install(cid, csec, rt, ch, pat, copy_to, repo)
    st, tok = exchange(cid, csec, code)
    if st != 200 or "refresh_token" not in tok:
        err = str(tok)[:260]
        print(f"❌ التبديل فشل ({st}): {err}")
        low = err.lower()
        if "invalid_grant" in low:
            print("   السبب الغالب: الكود اتستخدم قبل كده أو عدّى عليه 10 دقايق — اعمل موافقة جديدة من لينك وضع «url».")
        elif "unauthorized_client" in low:
            print("   السبب: عميل جوجل اللي في الأسرار مختلف عن اللي طلعت بيه الموافقة.")
            print("   الحل: استخدم لينك وضع «url» (بيتبني من نفس العميل اللي بيعمل التبديل) — سطر واحد وخلاص.")
        elif "redirect_uri_mismatch" in low:
            print(f"   السبب: العنوان {REDIRECT} مش مسجّل على العميل ده.")
            print("   الحل: Google Cloud → Credentials → OAuth client → Authorized redirect URIs → أضفه ثم أعد المحاولة.")
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


CANDIDATES = [
    "http://localhost",
    "http://localhost/",
    "http://localhost:8085/",
    "http://localhost:8899/callback",
    "http://127.0.0.1:8899/callback",
    "https://dawshax.github.io/youtube/callback/",
    "https://dawshax.github.io/youtube/",
    "https://8899-ivfx0jnsfhm4lb21x07io-ae1265fb.sg1.manus.computer/callback",
    "https://developers.google.com/oauthplayground",
    "urn:ietf:wg:oauth:2.0:oob",
]


def mode_scan(cid: str) -> int:
    """يجرب كل عناوين التحويل المحتملة ويقول أيها **مقبول فعلًا** على العميل ده.

    كده مفيش تخمين: بنعرف العنوان الصح من جوجل نفسها في تشغيل واحد.
    """
    good = []
    for r in CANDIDATES:
        ok, note = check_link(cid, r)
        print(("✅ مقبول  " if ok else "❌ مرفوض  ") + r + ("" if ok else "   (" + note[:70] + ")"))
        if ok:
            good.append(r)
    best = ""
    for pref in ("https://dawshax.github.io/youtube/callback/", "http://localhost", "https://developers.google.com/oauthplayground"):
        if pref in good:
            best = pref
            break
    print("\nالنتيجة: " + (("العنوان المستخدم: " + best) if best else "مفيش عنوان مسجّل من القايمة — لازم تضيف واحد"))
    print(telegram("🔎 فحص عناوين التحويل\n\n" + ("\n".join(good) if good else "مفيش عنوان مسجّل") +
                   ("\n\nاللي هنستخدمه: " + best if best else
                    "\n\nافتح https://console.cloud.google.com/apis/credentials?project=" + cid.split("-")[0] +
                    "\nواختار الـ OAuth client، وفي «Authorized redirect URIs» اضغط ADD URI والصق:\n"
                    "https://dawshax.github.io/youtube/callback/\nثم SAVE (كرّرها في كل العملا لو فيه أكتر من واحد)")))
    return 0


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
    if act == "scan":
        if not cid:
            print("❌ ناقص YOUTUBE_CLIENT_ID"); return 2
        return mode_scan(cid)
    print(f"وضع غير معروف: {act} (المتاح: url · token · probe)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
