"""⚙️ ضبط القناة للخوارزمية — Dollars Studio

    python tools/channel_setup.py                     # يعرض الحالة الحالية بس
    python tools/channel_setup.py --apply             # يطبّق الوصف + الكلمات المفتاحية + البلد + اللغة
    python tools/channel_setup.py --apply --name "NoVa Calm"
    python tools/channel_setup.py --playlists         # ينشئ بلايليستات لكل نوع + يحط الفيديوهات

بيحتاج توكن القناة (نفس مفاتيح النشر) — من غير مشروع جوجل جديد.
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.parse
import urllib.error
import urllib.request

sys.path[:] = [q for q in sys.path if pathlib.Path(q or ".").resolve() != pathlib.Path(__file__).resolve().parent]
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import publish  # noqa: E402

API = "https://www.googleapis.com/youtube/v3"

# 🎯 هوية القناة للنيتش (نوم · راحة · تركيز · ASMR · مُرضي للعين)
DESC = """Daily short videos from around the world — oddly satisfying moments, ASMR, animals, nature,
space, food, city life and quick facts. Original edits, real licensed footage, sound you can feel.

🌍 New videos every day · playlists for every mood

Footage and music are used under free licenses (CC0 / CC-BY / public domain) — credited in every description.
Subtitles in many languages. Business: dawshax@gmail.com
"""

KEYWORDS = ("oddly satisfying,satisfying video,asmr,asmr no talking,animals,funny pets,nature relax,"
            "space,science facts,food closeup,macro,slow motion,shorts,daily shorts,relaxing video,"
            "nature sounds,water sounds,background video,ambience,vertical video,4k shorts")

COUNTRY = "US"
LANG = "en"


def _req(method: str, path: str, token: str, body: dict | None = None, params: dict | None = None) -> dict:
    url = f"{API}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json",
                                          "User-Agent": "DollarsStudio/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def token() -> str | None:
    for prj in publish.all_projects():
        try:
            t = publish.access_token(prj)
            if t:
                return t
        except Exception:
            continue
    return None


def show(tok: str) -> dict:
    d = _req("GET", "channels", tok, params={"part": "snippet,statistics,brandingSettings", "mine": "true"})
    it = (d.get("items") or [{}])[0]
    sn, st = it.get("snippet") or {}, it.get("statistics") or {}
    ch = (it.get("brandingSettings") or {}).get("channel") or {}
    print("📺 القناة:", sn.get("title"), "|", it.get("id"))
    print("👥", st.get("subscriberCount"), "مشترك · 👁️", st.get("viewCount"), "مشاهدة · 🎬", st.get("videoCount"), "فيديو")
    print("🌍 البلد:", ch.get("country") or "❌ مش محدّد")
    print("🗣️ اللغة:", ch.get("defaultLanguage") or "❌ مش محددة")
    print("🔑 كلمات القناة:", (ch.get("keywords") or "❌ مفقودة")[:150])
    print("📄 الوصف:", ((ch.get("description") or "❌ مفقود")[:150]).replace("\n", " "))
    return it


def apply(tok: str, name: str | None = None) -> dict:
    """يضبط هوية القناة: وصف · كلمات مفتاحية · بلد · لغة (واسم لو اتبعت)."""
    cur = _req("GET", "channels", tok, params={"part": "brandingSettings,snippet", "mine": "true"})
    it = (cur.get("items") or [{}])[0]
    base = dict(it.get("brandingSettings") or {})
    chan = dict(base.get("channel") or {})
    chan.update({"description": DESC, "keywords": KEYWORDS, "country": COUNTRY,
                 "defaultLanguage": LANG})
    if name:
        chan["title"] = name
    body = {"id": it.get("id"), "brandingSettings": {**base, "channel": chan}}
    try:
        out = _req("PUT", "channels", tok, body=body, params={"part": "brandingSettings"})
        print("✅ الضبط اتطبق")
        return out
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            pass
        print(f"⚠️ القناة رفضت الضبط ({e.code}): {detail[:180]}")
        # محاولة أخيرة: أقل حقول ممكنة (وصف + كلمات فقط)
        try:
            mini = {"id": it.get("id"), "brandingSettings": {"channel": {
                "description": DESC, "keywords": KEYWORDS, "country": COUNTRY}}}
            out = _req("PUT", "channels", tok, body=mini, params={"part": "brandingSettings"})
            print("✅ الضبط اتطبق (نسخة مختصرة)")
            return out
        except urllib.error.HTTPError as e2:
            d2 = ""
            try:
                d2 = json.loads(e2.read().decode("utf-8")).get("error", {}).get("message", "")
            except Exception:
                pass
            print(f"❌ الضبط فشل ({e2.code}): {d2[:180]}")
            return {}
        except Exception as e3:
            print("❌ الضبط فشل:", type(e3).__name__)
            return {}


def playlists(tok: str, limit_titles: int = 400) -> int:
    """ينشئ بلايليست لكل نوع ويوزّع الفيديوهات المنشورة عليها."""
    from engine import genres as _gg
    import json as _j
    pub = _j.loads((ROOT / "state" / "published.json").read_text(encoding="utf-8")) if \
        (ROOT / "state" / "published.json").exists() else {"videos": []}
    made = 0
    try:
        gids = list((_gg.GENRES or {}).keys())
    except Exception:
        gids = []
    for gid in gids[:14]:
        try:
            pid = publish.playlist_id(gid.replace("_", " ").title(), token=tok)
        except Exception:
            pid = None
        if not pid:
            continue
        made += 1
        rows = [v for v in pub.get("videos", []) if (v.get("features") or {}).get("genre") == gid][-40:]
        for v in rows:
            try:
                publish.add_to_playlist(v.get("video_id"), pid, token=tok)
            except Exception:
                pass
    print(f"✅ بلايليستات: {made}")
    return made


def main() -> int:
    tok = token()
    if not tok:
        print("❌ مفيش توكن قناة (مفاتيح النشر)")
        return 1
    show(tok)
    if "--apply" in sys.argv:
        name = None
        if "--name" in sys.argv:
            i = sys.argv.index("--name")
            name = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
        apply(tok, name=name)
        show(tok)
    if "--playlists" in sys.argv:
        playlists(tok)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
