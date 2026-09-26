
"""بوابة الجودة: تمنع نشر أي فيديو ساكن/بلا صوت/سودة."""
from engine import quality, publish


def test_gate_passes_unreadable_file(tmp_path):
    """ملف مش فيديو أصلًا (مش ناتج الرندر) مايوقفش النشر — بس الفيديو المقروء البايظ يتوقف."""
    f = tmp_path / "fake.mp4"; f.write_bytes(b"\x00" * 2048)
    ok, rep = quality.gate(f)
    assert ok is True and rep.get("unreadable") is True


def test_gate_reports_check_list(tmp_path, monkeypatch):
    def fake_inspect(video, **kw):
        return {"checks": [("فيه حركة فعلية", True, "ok"), ("فيه صوت", True, "ok")], "pass": True}
    monkeypatch.setattr(quality, "inspect", fake_inspect)
    ok, rep = quality.gate("x.mp4")
    assert ok is True and rep["pass"] is True


def test_gate_blocks_on_first_failure(monkeypatch):
    def fake_inspect(video, **kw):
        return {"checks": [("فيه حركة فعلية", False, "متوسط الحركة 0.0001"), ("فيه صوت", True, "ok")],
                "pass": False, "resolution": "720x1280", "motion": 0.0001, "black_ratio": 0.02}
    monkeypatch.setattr(quality, "inspect", fake_inspect)
    ok, rep = quality.gate("x.mp4")
    assert ok is False and "فيه حركة فعلية" in rep["failed"]


def test_srt_is_valid():
    srt = publish.build_srt([{"at": 1.5, "dur": 2, "text": "Hello"}, {"at": 4, "dur": 2, "text": "World"}])
    assert "00:00:01,500 --> 00:00:03,500" in srt and "Hello" in srt and srt.count("-->") == 2
