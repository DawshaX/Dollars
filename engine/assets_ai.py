"""
🖼️ توليد أصول الشخصيات بالذكاء الاصطناعي (طبقات مجانية) — Dollars Studio
========================================================================
بنستخدم الطبقات المجانية المتاحة لبناء **ورقة شخصية** (Character Sheet) لكل شخصية:
أوضاع مختلفة (أمامي · جانبي · تعبيرات) ⇒ الشخصية تفضل **هي هي** في كل فيديو.

الطبقات (بالترتيب — اللي متاح بيشتغل، والباقي بيتخطّى بلا ما يوقف الشغل):
  1. Cloudflare Workers AI · FLUX.1 Schnell — **10,000 neurons/يوم مجانًا** (≈170–230 صورة)
     يحتاج: متغيّرات `CF_ACCOUNT_ID` و `CF_API_TOKEN` (بلا كارت بنك).
  2. Pollinations.ai — بلا مفتاح خالص (حدود أخف + علامة مائية).

⚠️ قواعد ملزمة (من docs/RIGHTS.md): كل برومبت لازم يطلب **تصميم أصلي** وممنوع أي شبه
بشخص حقيقي أو علامة محمية، وممنوع نص على الصورة (نصنا بنكتبه إحنا).

الواجهة:
    from engine import assets_ai
    assets_ai.available()                    # إيه المتاح دلوقتي
    assets_ai.build_all()                    # أوراق لكل الشخصيات
    assets_ai.build_one("nono")              # شخصية واحدة
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "characters"

POSES = {
    "front": "front view, full body, standing, feet visible, symmetrical pose",
    "side": "side profile view, full body, walking pose",
    "happy": "front view, happy expression, big smile, eyes joyful",
    "sad": "front view, sad expression, droopy eyes",
    "jump": "dynamic jumping pose, mid-air, arms up",
}
STYLE = ("cute original 2D animation character, flat vector style, thick clean outlines, "
         "soft warm lighting, plain pastel background, centered, full character visible, "
         "no text, no watermark, original design, not resembling any existing brand character "
         "or real person")


def _prompt(character: dict, pose: str) -> str:
    base = character.get("image_prompt") or (
        f"cute original 2D animation character, {character.get('type','creature')}, "
        f"{character.get('look','soft shapes')}")
    return f"{base}, {POSES[pose]}, {STYLE}"


# ───────────────────────────── الطبقات ─────────────────────────────

def _cloudflare(prompt: str, timeout: int = 90) -> bytes | None:
    acc = os.environ.get("CF_ACCOUNT_ID")
    tok = os.environ.get("CF_API_TOKEN")
    if not (acc and tok):
        return None
    url = (f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/"
           f"@cf/black-forest-labs/flux-1-schnell")
    body = json.dumps({"prompt": prompt, "steps": 6}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        if data.get("result", {}).get("image"):
            return base64.b64decode(data["result"]["image"])
        if data.get("success") and isinstance(data.get("result"), str):
            return base64.b64decode(data["result"])
    except Exception:
        return None
    return None


def _pollinations(prompt: str, timeout: int = 90) -> bytes | None:
    q = urllib.parse.quote(prompt[:900])
    url = f"https://image.pollinations.ai/prompt/{q}?width=768&height=768&nologo=true&model=flux"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DollarsStudio/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
        return data if len(data) > 5000 else None
    except Exception:
        return None


PROVIDERS = (("cloudflare", _cloudflare), ("pollinations", _pollinations))


def available(probe: bool = False) -> dict:
    """إيه المتاح: نشوف المفاتيح، ولو probe=True بنجرّب طبقة صغيرة فعليًا."""
    rows = {
        "cloudflare": {"configured": bool(os.environ.get("CF_ACCOUNT_ID") and os.environ.get("CF_API_TOKEN")),
                       "limit": "10,000 neurons/يوم ≈ 170–230 صورة (مجانًا للأبد)"},
        "pollinations": {"configured": True, "limit": "بلا مفتاح · حدود أخف · علامة مائية"},
    }
    if probe:
        for name, fn in PROVIDERS:
            if name == "cloudflare" and not rows[name]["configured"]:
                continue
            ok = fn("a simple blue circle on white background, no text") is not None
            rows[name]["works"] = ok
            break
    return rows


def generate(prompt: str, path, prefer: str | None = None, quiet: bool = True) -> pathlib.Path | None:
    """يجرّب الطبقات بالترتيب ويحفظ أول صورة ناجحة."""
    path = pathlib.Path(path)
    order = ([prefer] if prefer else []) + [n for n, _ in PROVIDERS if n != prefer]
    for name in order:
        fn = dict(PROVIDERS).get(name)
        if not fn:
            continue
        data = fn(prompt)
        if data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if not quiet:
                print(f"✅ {path.name} ({name})")
            return path
        time.sleep(1.0)
    if not quiet:
        print(f"⚠️ مفيش طبقة متاحة دلوقتي — {path.name} اتخطّى")
    return None


def build_one(character_id: str, poses=None, path=None, quiet=False) -> dict:
    data = json.loads(pathlib.Path(path or ROOT / "content" / "characters.json").read_text(encoding="utf-8"))
    ch = next((c for c in data.get("characters", []) if c.get("id") == character_id), None)
    if not ch:
        raise KeyError(f"مفيش شخصية بالمعرّف {character_id}")
    made, out_dir = [], OUT / character_id
    for pose in (poses or list(POSES)):
        p = out_dir / f"{pose}.png"
        if p.exists():
            made.append(str(p))
            continue
        res = generate(_prompt(ch, pose), p, quiet=quiet)
        if res:
            made.append(str(res))
    if made:
        (out_dir / "sheet.json").write_text(json.dumps({
            "character": character_id, "name": ch.get("name"), "poses": list(poses or POSES),
            "note": "أوراق شخصية مولّدة بطبقات مجانية — بتستخدم كمرجع بصري للثبات",
            "license": "owned-generated (لا تحمل أي شبه بأشخاص حقيقيين أو علامات محمية)",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"character": character_id, "images": made, "count": len(made)}


def build_all(limit: int | None = None, quiet: bool = True) -> dict:
    data = json.loads((ROOT / "content" / "characters.json").read_text(encoding="utf-8"))
    chars = data.get("characters", [])[:limit] if limit else data.get("characters", [])
    total, rows = 0, []
    for c in chars:
        r = build_one(c["id"], quiet=quiet)
        total += r["count"]
        rows.append(f"{c['name']}: {r['count']} صورة")
    return {"characters": len(chars), "images": total, "detail": rows}


if __name__ == "__main__":
    print("الطبقات المتاحة:", json.dumps(available(probe=True), ensure_ascii=False, indent=2))
    print(json.dumps(build_all(), ensure_ascii=False, indent=2))
