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
    assert c == {"client_id": "id", "client_secret": "secret", "refresh_token": "refresh"}
    assert publish.available()["ok"] is True


def test_snippet_and_status_follow_youtube_rules():
    md = meta.build({"pillar": "sleep", "kw": "Rain Sounds", "hours": 10})
    sn = publish._snippet(md)
    st = publish._status(md)
    assert len(sn["title"]) <= 100
    assert sn["categoryId"] == "10" and sn["defaultAudioLanguage"] == "zxx"
    assert st["selfDeclaredMadeForKids"] is False        # مهم للإعلانات
    assert st["privacyStatus"] == "public"
    assert st["embeddable"] is True


def test_notify_is_quiet_without_keys(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert publish.notify("test") is False
