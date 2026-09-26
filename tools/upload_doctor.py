#!/usr/bin/env python3
"""
🩺 دكتور الرفع — يشخّص سبب رفض يوتيوب للرفع في ثواني (بدون رندر مصنع كامل).

بيجرّب مصفوفة بيانات (من الأبسط للأكمل) على نفس الميكانيكا بالظبط،
وكل محاولة ناجحة بتتمسح فورًا — عشان ميبقاش فيه أي حاجة وهمية على القناة.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import urllib.error
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


TITLE = "Upload Doctor Test"


def variants() -> list[tuple[str, dict, str]]:
    """(اسم، body، باراميترات إضافية) — من الأبسط للأكمل."""
    return [
        ("1) أسوأ احتمال: عنوان بس",
         {"snippet": {"title": TITLE, "categoryId": "22"}}, ""),
        ("2) + status (خصوصية خاصة)",
         {"snippet": {"title": TITLE, "categoryId": "22"},
          "status": {"privacyStatus": "private"}}, ""),
        ("3) + الحقول اللي المصنع بيبعتها (license/embeddable/publicStats/للأطفال)",
         {"snippet": {"title": TITLE, "categoryId": "22"},
          "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False,
                     "license": "youtube", "embeddable": True, "publicStatsViewable": True}}, ""),
        ("4) + وصف ووسوم",
         {"snippet": {"title": TITLE, "categoryId": "22", "description": "test desc",
                      "tags": ["test", "doctor"]},
          "status": {"privacyStatus": "private"}}, ""),
        ("5) + categoryId 10 (مزيكا زي المصنع)",
         {"snippet": {"title": TITLE, "categoryId": "10", "description": "test desc"},
          "status": {"privacyStatus": "private"}}, ""),
        ("6) + defaultLanguage en بس",
         {"snippet": {"title": TITLE, "categoryId": "10", "defaultLanguage": "en"},
          "status": {"privacyStatus": "private"}}, ""),
        ("7) + defaultAudioLanguage zxx (زي المصنع بالظبط)",
         {"snippet": {"title": TITLE, "categoryId": "10", "defaultLanguage": "en",
                      "defaultAudioLanguage": "zxx"},
          "status": {"privacyStatus": "private"}}, ""),
        ("8) بيانات المصنع الكاملة على الميكانيكا دي",
         {"snippet": publish._snippet({"titles": [TITLE], "description": "d", "tags": ["t"],
                                       "category_id": "10", "default_language": "en"}),
          "status": publish._status({"upload_defaults": {"visibility": "private"}})}, ""),
        ("9) زي 8 بس من غير هيدر X-Upload-Content-*",
         {"snippet": publish._snippet({"titles": [TITLE], "description": "d", "tags": ["t"],
                                       "category_id": "10", "default_language": "en"}),
          "status": publish._status({"upload_defaults": {"visibility": "private"}})}, "NOHDR"),
    ]


def delete(video_id: str, token: str) -> None:
    req = urllib.request.Request(f"{publish.API}/videos?id={video_id}",
                                 headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"   🧹 اتمسح الاختباري ({r.status})")
    except Exception as e:
        print("   ⚠️ ممسحناهوش:", type(e).__name__, str(e)[:200])


def main() -> int:
    ok = publish.available(probe=True)
    print("🎫 التوكن:", "✅ شغال" if ok["ok"] else "❌ " + ok["reason"])
    if not ok["ok"]:
        return 1
    token = publish.access_token()
    path = tiny_video()
    print(f"🎞️ فيديو اختباري: {path} ({path.stat().st_size/1024:.0f} KB)")
    print("📊 الحصة:", json.dumps(publish.quota_report()["projects"], ensure_ascii=False))

    winner = None
    for name, body, flag in variants():
        kw = {"headers": {"X-Upload-Content-Length": None}} if False else {}
        if flag == "NOHDR":
            kw = {"headers": {"X-Upload-Content-Length": "", "X-Upload-Content-Type": ""}}
        print(f"\n— {name} —")
        try:
            res = publish.put_video(path, body, token=token, **kw)
            print("   ✅ نجح:", res["id"], res["url"])
            winner = winner or name
            delete(res["id"], token)
        except Exception as e:
            print("   ❌", str(e)[:400])
    print("\n🎯 أول تركيبة نجحت:", winner or "مفيش — المشكلة في الميكانيكا نفسها (مش البيانات)")
    return 0 if winner else 2


if __name__ == "__main__":
    raise SystemExit(main())
