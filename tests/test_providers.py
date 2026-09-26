"""اختبارات طبقة المزوّدين: مايخدعش — لو مفيش مفتاح أو الشبكة واقعة، يرجّع فاضي بهدوء."""
from engine import providers


def test_available_reports_booleans():
    a = providers.available()
    assert all(isinstance(v, bool) for v in a.values())
    assert a["wikimedia"] and a["youtube_suggest"], "المصادر المجانية من غير مفتاح لازم تبان جاهزة"


def test_missing_keys_return_empty_not_crash(monkeypatch):
    for name in ("PIXABAY_KEY", "PIXABAY_API_KEY", "PEXELS_API_KEY", "PEXELS", "GROQ_API_KEY",
                 "GEMINI_API_KEY", "GNEWS_API_KEY", "CURRENTS_API_KEY", "FREESOUND_ID"):
        monkeypatch.delenv(name, raising=False)
    assert providers.pixabay_images("x") == []
    assert providers.pexels_videos("x") == []
    assert providers.groq("x") == "" and providers.gemini("x") == "" and providers.llm("x") == ""
    assert providers.gnews("x") == [] and providers.currents("x") == []
    assert providers.freesound("x") == []


def test_network_failure_is_silent(monkeypatch):
    def boom(*a, **k):
        raise OSError("الشبكة واقعة")

    monkeypatch.setattr(providers.urllib.request, "urlopen", boom)
    assert providers.wikimedia_images("x") == []
    assert providers.openverse_images("x") == []
    assert providers.nasa_images("x") == []
    assert providers.youtube_suggest("x") == []
    assert providers.restcountries("Egypt") == {}


def test_reference_visuals_collects_from_any_working_source(monkeypatch):
    monkeypatch.setattr(providers, "pixabay_images", lambda q, per=6: [{"source": "pixabay", "url": "u1"}])
    monkeypatch.setattr(providers, "pexels_images", lambda q, per=6: [])
    monkeypatch.setattr(providers, "openverse_images", lambda q, per=6: [{"source": "openverse", "url": "u2"}])
    monkeypatch.setattr(providers, "wikimedia_images", lambda q, per=6: [{"source": "wikimedia", "url": "u3"}])
    got = providers.reference_visuals("rain", per=2)
    assert [g["source"] for g in got] == ["pixabay", "openverse", "wikimedia"]
