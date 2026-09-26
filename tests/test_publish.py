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
    monkeypatch.setattr(publish, "ROLES_FILE", tmp_path / "roles.json")
    assert [c["project"] for c in publish.all_projects()] == [1, 2]
    assert publish.remaining_capacity() == 12, "مشروعان = ١٢ رفعة/يوم"
    for _ in range(6):                              # نستهلك المشروع الأول بالكامل
        publish.mark_upload(1, True)
    assert publish.pick_project()["project"] == 2   # بيتحوّل للتاني لوحده
    rep = publish.quota_report()
    assert rep["projects"]["1"]["uploads_left"] == 0 and rep["projects"]["2"]["uploads_left"] == 6
    for _ in range(6):
        publish.mark_upload(2, True)
    assert publish.pick_project() is None, "لما الحصة تخلص في الكل لازم يوقف"
    assert publish.remaining_capacity() == 0


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


def test_prune_role_reserves_project_for_deleting(monkeypatch, tmp_path):
    """مشروع محجوز للمسح: مبنرفعش بيه، وبنسحب منه ٥٠ وحدة لكل فيديو قديم."""
    monkeypatch.setattr(publish, "QUOTA_FILE", tmp_path / "q.json")
    monkeypatch.setattr(publish, "ROLES_FILE", tmp_path / "roles.json")
    monkeypatch.setattr(publish, "PROJECTS_FILE", tmp_path / "prj.json")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "id1")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "s1")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "r1")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID_2", "id2")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET_2", "s2")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_2", "r2")
    (tmp_path / "prj.json").write_text('{"usable": ["2"]}', encoding="utf-8")
    publish.set_role(2, "prune")
    assert publish.role_of(2) == "prune" and publish.role_of(1) == "publish"
    assert [c["project"] for c in publish.prune_projects()] == [2]
    publish.mark_units(2, publish.DELETE_UNITS * 3)
    rep = publish.quota_report()
    assert rep["projects"]["2"]["deletes_left"] == 200 - 3, "٣ مسح = ١٥٠ وحدة"
    assert publish.remaining_capacity() == 6, "المشروع المحجوز مش بيتحسب للنشر"
    publish.mark_units(1, publish.DAILY_UNITS)
    assert publish.pick_project() is None


def test_quota_stop_and_resume_notices_are_sent_once(monkeypatch, tmp_path):
    monkeypatch.setattr(publish, "NOTICE_FILE", tmp_path / "notice.json")
    monkeypatch.setattr(publish, "QUOTA_FILE", tmp_path / "q.json")
    monkeypatch.setattr(publish, "PROJECTS_FILE", tmp_path / "prj.json")
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "a")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "b")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "c")
    sent = []
    monkeypatch.setattr(publish, "notify", lambda t: sent.append(t) or True)
    publish.quota_stop_notice(); publish.quota_stop_notice()
    assert len(sent) == 1 and "الحصة" in sent[0] or "حصة" in sent[0]
    publish.quota_resume_notice(); publish.quota_resume_notice()
    assert len(sent) == 2, "رسالة الرجوع تتبعت مرة واحدة بس"


def test_prune_never_touches_new_factory_videos(monkeypatch, tmp_path):
    """أهم قاعدة: المكنسة تمسح القديم بس — الجديد ممنوع تمامًا."""
    from engine import prune
    monkeypatch.setattr(prune, "STATE", tmp_path / "prune.json")
    pub = tmp_path / "published.json"
    pub.write_text('{"videos": [{"video_id": "NEW1", "title": "جديد"}]}', encoding="utf-8")
    monkeypatch.setattr(prune.pathlib, "Path", lambda *a: pub if a and a[0] == "state/published.json" else pathlib.Path(*a))
    keep = prune._keep_ids()
    assert "NEW1" in keep, "فيديوهات المصنع الجديد لازم تتحفظ من المسح"

    class FakeResp:
        status = 204

    def fake_urlopen(req, timeout=0):
        return FakeResp()

    items = [{"contentDetails": {"videoId": "OLD1"},
              "snippet": {"title": "قديم", "publishedAt": "2026-09-17T10:00:00Z"}},
             {"contentDetails": {"videoId": "NEW1"},
              "snippet": {"title": "جديد", "publishedAt": "2026-09-26T04:00:00Z"}}]

    class Ctx:
        def __init__(self, d): self.d = d
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return __import__("json").dumps(self.d).encode()

    monkeypatch.setattr(prune.publish.urllib.request, "urlopen", lambda req, timeout=0: Ctx({"items": items}))
    olds = prune.list_old("tok", "UCG9g_26H65D3FahqyiYPHAw")
    assert [o["id"] for o in olds] == ["OLD1"], "القديم بس"
