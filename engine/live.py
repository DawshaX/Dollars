"""
📡 البث الحي — المصنع يحكي كل خطوة بيعملها لحظة بلحظة.

ليه؟ لأن أي تعليق أو خطأ لازم يبان **فورًا** مش بعد ما الشغل يخلص.
بيكتب في Issue رقم LIVE_ISSUE (لو موجود) وفي الـlog العادي برضه.

الاستخدام:
    from engine import live
    live.say("🎬 بدأت رندر ...")
"""
from __future__ import annotations

import json
import os
import pathlib
import urllib.request

LOG_FILE = pathlib.Path("state/live.md")


def _issue_post(text: str) -> None:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    num = os.environ.get("LIVE_ISSUE")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (tok and num and repo):
        return
    body = json.dumps({"body": text}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues/{num}/comments", data=body,
        headers={"Authorization": f"token {tok}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception:
        pass                                   # البث max يفشل، مايوقفش الشغل أبدًا


def say(text: str, file: bool = True) -> None:
    print(text, flush=True)
    _issue_post(text)
    if file:
        try:
            with LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except Exception:
            pass
