"""اختبارات توليد أوراق الشخصيات (بلا شبكة — بطبقات وهمية)."""
import json

import pytest

from engine import assets_ai


def test_available_reports_providers():
    rows = assets_ai.available()
    assert "cloudflare" in rows and "pollinations" in rows
    assert rows["pollinations"]["configured"] is True           # بلا مفتاح
    assert isinstance(rows["cloudflare"]["configured"], bool)   # حسب المتغيّرات


def test_prompt_is_original_and_textless():
    ch = {"id": "x", "type": "clay ball", "look": "soft brown ball with big eyes"}
    p = assets_ai._prompt(ch, "front")
    assert "original design" in p and "no text" in p
    assert "not resembling" in p
    assert "front view" in p


def test_generate_uses_first_working_provider(tmp_path, monkeypatch):
    calls = []

    def fake_ok(prompt, timeout=90):
        calls.append("cloudflare")
        return b"x" * 9000

    monkeypatch.setattr(assets_ai, "PROVIDERS", (("cloudflare", fake_ok),))
    p = assets_ai.generate("prompt", tmp_path / "a.png")
    assert p and p.exists() and p.read_bytes() == b"x" * 9000
    assert calls == ["cloudflare"]


def test_generate_falls_back_when_first_fails(tmp_path, monkeypatch):
    def dead(prompt, timeout=90):
        return None

    def good(prompt, timeout=90):
        return b"y" * 9000

    monkeypatch.setattr(assets_ai, "PROVIDERS", (("cloudflare", dead), ("pollinations", good)))
    monkeypatch.setattr(assets_ai.time, "sleep", lambda s: None)
    p = assets_ai.generate("prompt", tmp_path / "b.png")
    assert p and p.read_bytes() == b"y" * 9000


def test_generate_returns_none_when_all_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(assets_ai, "PROVIDERS", (("cloudflare", lambda p, timeout=90: None),))
    monkeypatch.setattr(assets_ai.time, "sleep", lambda s: None)
    assert assets_ai.generate("prompt", tmp_path / "c.png") is None


def test_build_one_writes_sheet(tmp_path, monkeypatch):
    data = {"characters": [{"id": "nono", "name": "Nono", "type": "clay", "look": "ball",
                            "image_prompt": "cute clay ball character"}]}
    cj = tmp_path / "characters.json"
    cj.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(assets_ai, "OUT", tmp_path / "chars")
    monkeypatch.setattr(assets_ai, "generate",
                        lambda prompt, path, prefer=None, quiet=True: (path.parent.mkdir(parents=True, exist_ok=True),
                                                                      path.write_bytes(b"z" * 6000), path)[-1])
    r = assets_ai.build_one("nono", poses=["front", "side"], path=cj, quiet=True)
    assert r["count"] == 2
    sheet = json.loads((tmp_path / "chars" / "nono" / "sheet.json").read_text(encoding="utf-8"))
    assert sheet["name"] == "Nono" and "owned-generated" in sheet["license"]


def test_build_one_unknown_character_fails(tmp_path):
    cj = tmp_path / "characters.json"
    cj.write_text('{"characters": []}', encoding="utf-8")
    with pytest.raises(KeyError):
        assets_ai.build_one("ghost", path=cj)


def test_existing_images_are_not_regenerated(tmp_path, monkeypatch):
    cj = tmp_path / "characters.json"
    cj.write_text(json.dumps({"characters": [{"id": "koko", "name": "Koko"}]}), encoding="utf-8")
    monkeypatch.setattr(assets_ai, "OUT", tmp_path / "chars")
    (tmp_path / "chars" / "koko").mkdir(parents=True)
    (tmp_path / "chars" / "koko" / "front.png").write_bytes(b"a" * 6000)
    called = []
    monkeypatch.setattr(assets_ai, "generate", lambda *a, **k: called.append(1))
    r = assets_ai.build_one("koko", poses=["front"], path=cj, quiet=True)
    assert r["count"] == 1 and not called                # استخدم الموجودة
