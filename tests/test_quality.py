"""بوابة الجودة — السياسة الجديدة: بتحذّر مش بتمنع (إلا الملف التالف).

السبب (حادثة ٢٦/٩): البوابة القديمة رفضت ١٠ فيديوهات في ساعة —
فيديوهات نوم طويلة «ساكنة» (وده مقصود) وحكايات «أبعادها مختلفة» (وده صح).
النشر واقف دلوقتي على الطويلة اللي في الطابور عشان الباج ده.
"""
from engine import quality, publish


def _video(tmp_path, size=20_000):
    f = tmp_path / "v.mp4"; f.write_bytes(b"\x00" * size); return f


def test_gate_blocks_missing_or_broken_file(tmp_path):
    """ملف مش موجود أو أصغر من ١٠ كيلو = تالف ⇒ مايتنشرش."""
    ok, rep = quality.gate(tmp_path / "nope.mp4")
    assert ok is False and rep["fatal"] == ["الملف تالف"]
    tiny = tmp_path / "tiny.mp4"; tiny.write_bytes(b"\x00" * 900)
    ok, rep = quality.gate(tiny)
    assert ok is False


def test_gate_publishes_big_unreadable_file(tmp_path, monkeypatch):
    """ملف كبير بس الفحص مش قادر يقراه (بروب على ملف ضخم) ⇒ **ينشر** — عشان النشر مايتوقفش."""
    monkeypatch.setattr(quality, "inspect",
                        lambda video, **kw: {"checks": [("الأبعاد", False, "0x0")], "pass": False,
                                             "resolution": "0x0", "motion": None, "black_ratio": None})
    ok, rep = quality.gate(_video(tmp_path, size=300_000))
    assert ok is True and rep["warnings"]


def test_gate_publishes_with_warnings(tmp_path, monkeypatch):
    """فيديو سليم فيه ملاحظات (ثبات/أبعاد) ⇒ **ينشر** والملاحظات تتسجّل."""
    def fake_inspect(video, **kw):
        return {"checks": [("مفيش ثبات طويل", False, "أطول ثبات 9.0 ثانية"), ("فيه صوت", True, "ok")],
                "pass": False, "resolution": "1920x1080", "motion": 0.01, "black_ratio": 0.35}
    monkeypatch.setattr(quality, "inspect", fake_inspect)
    ok, rep = quality.gate(_video(tmp_path))
    assert ok is True, "الملاحظات لازم ما توقفش النشر"
    assert rep["warnings"] == ["مفيش ثبات طويل"] and rep["fatal"] == []


def test_gate_strict_mode_for_manual_qa(tmp_path, monkeypatch):
    """الفحص اليدوي (strict=True): أي ملاحظة تبقى مانعة — لـ video_doctor."""
    monkeypatch.setattr(quality, "inspect",
                        lambda video, **kw: {"checks": [("فيه حركة فعلية", False, "0.0001")],
                                             "pass": False, "resolution": "720x1280",
                                             "motion": 0.0001, "black_ratio": 0.0})
    ok, rep = quality.gate(_video(tmp_path), strict=True)
    assert ok is False and "فيه حركة فعلية" in rep["failed"]


def test_gate_never_blocks_when_inspector_fails(tmp_path, monkeypatch):
    """لو أداة الفحص نفسها وقعت ⇒ ننشر (الفيديو اترندر فعلًا)."""
    def boom(video, **kw):
        raise RuntimeError("ffmpeg وقع")
    monkeypatch.setattr(quality, "inspect", boom)
    ok, rep = quality.gate(_video(tmp_path))
    assert ok is True and rep["warnings"]


def test_srt_is_valid():
    srt = publish.build_srt([{"at": 1.5, "dur": 2, "text": "Hello"}, {"at": 4, "dur": 2, "text": "World"}])
    assert "00:00:01,500 --> 00:00:03,500" in srt and "Hello" in srt and srt.count("-->") == 2
