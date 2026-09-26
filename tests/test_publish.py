"""اختبارات النشر: بيرفض بلطف لو مفيش توكن · بيبني البيانات الصح · بيمسك الأخطاء."""
import os

import pytest

from engine import meta, publish


def test_without_credentials_it_says_why(monkeypatch):
    for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN",
              "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    st = publish.available()
    assert st["ok"] is False and "توكن" in st["reason"]
    with pytest.raises(publish.PublishUnavailable):
        publish.access_token()


def test_credentials_read_from_env(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "refresh")
    c = publish.creds()
    assert c["client_id"] == "id" and c["client_secret"] == "secret" and c["refresh_token"] == "refresh"
    assert c["project"] == 1
    assert publish.available()["ok"] is True


def test_extra_projects_are_discovered_and_rotate(monkeypatch, tmp_path):
    """كل مشروع جوجل إضافي = حصة زيادة ⇒ النظام لازم يشوفه ويستعمله بالتبادل."""
    monkeypatch.setattr(publish, "QUOTA_FILE", tmp_path / "q.json")
    monkeypatch.setattr(publish, "PROJECTS_FILE", tmp_path / "prj.json")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "id1")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "s1")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "r1")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID_2", "id2")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET_2", "s2")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_2", "r2")
    (tmp_path / "prj.json").write_text('{"usable": ["2"]}', encoding="utf-8")   # اتأكد إنه على قناتنا
    assert [c["project"] for c in publish.all_projects()] == [1, 2]
    for _ in range(6):                              # نستهلك المشروع الأول بالكامل
        publish.mark_upload(1, True)
    assert publish.pick_project()["project"] == 2   # بيتحوّل للتاني لوحده
    rep = publish.quota_report()
    assert rep["projects"]["1"]["left"] == 0 and rep["projects"]["2"]["left"] == 6
    for _ in range(6):
        publish.mark_upload(2, True)
    assert publish.pick_project() is None, "لما الحصة تخلص في الكل لازم يوقف"


def test_quota_errors_are_detected():
    assert publish.is_quota_error("The user has exceeded the number of videos they may upload.")
    assert publish.is_quota_error("quotaExceeded")
    assert not publish.is_quota_error("invalid_grant")


def test_snippet_and_status_follow_youtube_rules():
    md = meta.build({"pillar": "sleep", "kw": "Rain Sounds", "hours": 10})
    sn = publish._snippet(md)
    st = publish._status(md)
    assert len(sn["title"]) <= 100
    assert sn["categoryId"] == "10" and "defaultAudioLanguage" not in sn
    assert st["selfDeclaredMadeForKids"] is False        # مهم للإعلانات
    assert st["privacyStatus"] == "public"
    assert st["embeddable"] is True


def test_notify_is_quiet_without_keys(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert publish.notify("test") is False


def test_never_send_broken_audio_language():
    """درس غالي: defaultAudioLanguage="zxx" بيرفض الرفع كله — لازم يتشال للأبد."""
    md = meta.build({"pillar": "sleep", "kw": "Rain Sounds", "kind": "short"})
    sn = publish._snippet(md)
    assert "defaultAudioLanguage" not in sn
    assert "zxx" not in __import__("json").dumps(sn)


def test_only_same_channel_projects_are_used(monkeypatch, tmp_path):
    """مشروع لقناة تانية ممنوع يتنشر بيه — لازم يتجاهله النظام."""
    monkeypatch.setattr(publish, "PROJECTS_FILE", tmp_path / "projects.json")
    monkeypatch.setattr(publish, "QUOTA_FILE", tmp_path / "q.json")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "id1")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "s1")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "r1")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID_2", "id2")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET_2", "s2")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_2", "r2")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID_3", "id3")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET_3", "s3")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_3", "r3")
    assert [c["project"] for c in publish.usable_projects()] == [1], "من غير تحقق: الأساسي بس"
    (tmp_path / "projects.json").write_text('{"usable": ["2"]}', encoding="utf-8")
    assert [c["project"] for c in publish.usable_projects()] == [1, 2], "المتحقق بس"
