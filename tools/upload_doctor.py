#!/usr/bin/env python3
"""
🩺 دكتور الرفع — يشخّص سبب رفض يوتيوب للرفع في ثواني (بدون رندر مصنع كامل).

- يعمل فيديو اختباري صغير (٢ ثانية) بنفس مواصفاتنا.
- يجرّب يرفعه ببيانات كاملة. لو يوتيوب رفض، يطبع **سبب الرفض الحقيقي** (reason) ويجرّب بيانات مبسطة.
- لو نجح: يمسح الفيديو الاختباري فورًا (عشان ميبقاش فيه حاجة وهمية على القناة).
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from engine import publish  # noqa: E402


def tiny_video(path="work/doctor_test.mp4") -> pathlib.Path:
    import imageio_ffmpeg
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y",
           "-f", "lavfi", "-i", "color=c=black:s=720x1280:d=3:r=30",
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-t", "3", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", str(p)]
    subprocess.run(cmd, check=True, capture_output=True)
    return p


FULL_MD = {
    "titles": ["اختبار الرفع · Upload Doctor (تتجاب فورًا)"],
    "description": "فيديو اختبار تلقائي للتأكد إن الرفع شغال — بيتحذف في نفس الدقيقة.",
    "tags": ["test", "dollars factory", "اختبار"],
    "category_id": "10",
    "default_language": "en",
    "upload_defaults": {"visibility": "private"},
    "made_for_kids": False,
    "thumbnail_texts": [],
    "playlist": None,
}


def try_upload(label: str, md: dict, path) -> dict | None:
    print(f"\n— محاولة: {label} —")
    try:
        res = publish.upload(path, md)
        print("✅ نجح:", res["id"], res["url"])
        return res
    except Exception as e:
        print("❌ فشل:", type(e).__name__, "|", str(e)[:700])
        return None


def delete(video_id: str, token: str) -> None:
    req = urllib.request.Request(
        f"{publish.API}/videos?id={video_id}",
        headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"🧹 اتمسح الاختباري ({r.status})")
    except Exception as e:
        print("⚠️ ممسحناهوش:", type(e).__name__, str(e)[:200])


def main() -> int:
    ok = publish.available(probe=True)
    print("🎫 التوكن:", "✅ شغال" if ok["ok"] else "❌ " + ok["reason"])
    if not ok["ok"]:
        return 1
    try:
        token = publish.access_token()
    except Exception as e:
        print("❌ مش قادر أجيب access token:", e)
        return 1

    path = tiny_video()
    print(f"🎞️ فيديو اختباري: {path} ({path.stat().st_size/1024:.0f} KB)")
    print(f"📊 حصة النهاردة: {json.dumps(publish.quota_report()['projects'], ensure_ascii=False)}")

    res = try_upload("بيانات كاملة (زي المصنع)", dict(FULL_MD), path)
    if res:
        delete(res["id"], token)
        print("\n🎉 الخلاصة: الرفع شغال تمام — المشكلة كانت في حاجة تانية.")
        return 0

    # مبسّط: من غير لغة صوت/لغة — لو نجح تبقى هي السبب
    simple = {k: v for k, v in FULL_MD.items() if k not in ("default_language",)}
    res = try_upload("بيانات مبسطة (من غير لغات)", dict(simple), path)
    if res:
        delete(res["id"], token)
        print("\n🎯 السبب اتحدد: حقول اللغة هي اللي كانت بترفض الرفع.")
        return 0
    print("\n🛑 لسه مرفوض — شوف سبب الرفض (reason) اللي فوق.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
