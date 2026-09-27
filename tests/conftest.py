"""⚙️ تجهيز الاختبارات: منع أي كتابة في حالة الإنتاج (state/) أو الرفع الحقيقي.

السبب: اختبارات كانت بتكتب في state/factory_log.md و published.json الحقيقية
فتلخبط سجل المصنع وسجّل نشر وهمي. دلوقتي كل اختبار بياخد مجلد حالة خاص.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """مجلد حالة مؤقت لكل اختبار + منع أي ترجمة/شبكة غير مقصودة."""
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DOLLARS_STATE", str(state))
    monkeypatch.setenv("DOLLARS_DEMAND", "0")        # من غير نداءات شبكة في الاختبارات
    monkeypatch.setenv("DOLLARS_LOOP", "0")
    monkeypatch.setenv("DOLLARS_SYNC", "0")
    try:
        from engine import factory
        monkeypatch.setattr(factory, "STATE", state, raising=False)
    except Exception:
        pass
    yield
