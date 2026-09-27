"""📨 فحص تليجرام — يتأكد إن الإشعارات بتوصل فعلًا وبإيه رقم الشات.

    python tools/telegram_test.py            # فحص + رسالة تجربة
    python tools/telegram_test.py --quiet    # فحص بدون رسالة

بيطبع: اسم البوت · الأرقام اللي البوت شايفها (getUpdates) · نتيجة الإرسال وسبب أي فشل.
مش بيطبع التوكن أبدًا. ولو الشات متسجّل غلط، بيصلّحه ويحفظه في state/telegram.json
عشان المصنع يبعت لوحده بعد كده.
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

sys.path[:] = [q for q in sys.path if pathlib.Path(q or ".").resolve() != pathlib.Path(__file__).resolve().parent]
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import publish  # noqa: E402


def _api(tok: str, method: str, data: dict | None = None) -> dict:
    url = f"https://api.telegram.org/bot{tok}/{method}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    quiet = "--quiet" in sys.argv
    tok = publish._env("TELEGRAM_BOT_TOKEN")
    if not tok:
        print("❌ مفيش TELEGRAM_BOT_TOKEN في البيئة")
        return 1
    try:
        me = _api(tok, "getMe").get("result") or {}
        print(f"🤖 البوت: @{me.get('username')} ({me.get('first_name')})")
    except Exception as e:
        print("❌ التوكن مش شغال:", type(e).__name__)
        return 1

    chat_env = publish._env("TELEGRAM_CHAT_ID", "TELEGRAM_ADMIN_CHAT_ID")
    print("🆔 الشات في الإعدادات:", chat_env or "مش متسجّل")
    try:
        ups = _api(tok, "getUpdates").get("result") or []
        found = []
        for u in ups:
            m = u.get("message") or u.get("channel_post") or {}
            c = m.get("chat") or {}
            if c.get("id") and c["id"] not in found:
                found.append(c["id"])
                print(f"   • رسالة من: {c.get('type')} · id={str(c['id'])[:4]}…{str(c['id'])[-3:]}"
                      f" · {c.get('username') or c.get('title') or c.get('first_name') or ''}")
        if not found:
            print("   (مفيش رسائل للبوت — اكتب له أي كلمة مرة واحدة وهو هيمسك الشات لوحده)")
    except Exception as e:
        print("⚠️ getUpdates فشل:", type(e).__name__)

    if quiet:
        return 0
    ok = publish.notify("✅ فحص تليجرام — الإشعارات شغالة، والمصنع هيبلّغك على كل نشر 🎬")
    print("📨 نتيجة الإرسال:", "وصلت ✅" if ok else "فشلت ❌ (السبب مطبوع فوق)")
    st = publish.TELEGRAM_STATE
    if st.exists():
        print("💾 محفوظ:", json.dumps(json.loads(st.read_text(encoding="utf-8")), ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
