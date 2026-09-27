"""
🏭 المصنع — Dollars Studio
==========================
ده اللي **بيشغّل نفسه**: يقرأ خطة العقل → يختار الدور → يطلّع الفيديو كامل (مونتاج + صوت +
غلاف + بيانات) → ينشره لو القناة مربوطة، ولو لأ **يحفظه في الطابور** ويكمّل.

التشغيل:
    python engine/factory.py --hourly            # شورت واحد (اللي جاي في الخطة)
    python engine/factory.py --hourly --count 3  # تلاتة
    python engine/factory.py --daily             # طويل (نوم 3/8/10 ساعات) + قصة
    python engine/factory.py --status            # تقرير المصنع
    python engine/factory.py --kind story --count 1

كل حاجة بتتسجّل في: state/produced.json (السجل) · state/queue.json (جاهز للنشر) · state/factory_log.md

مبادئ ملزمة (زي ما اتفقنا):
- مفيش حاجة مسروقة: كل مشهد/صوت/ملصق ملكنا.
- الإفصاح عن AI إلزامي في كل وصف (meta.validate بيمنع النشر لو ناقص).
- النشر بلا حد: كل ساعة شورت + طويلة يوميًا (وبالزيادة عند تعدد المشاريع).
- الفشل ممنوع يوقّف الطابور: أي خطأ يتسجّل والمصنع يكمّل.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import random
import sys
import time
import traceback
from datetime import date, datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import agent, editor, meta, photo, publish, visuals  # noqa: E402
from engine import clips

# ── حماية من تعارض الأسماء: مجلد السكربت بيتحط أول مسار الاستيراد لما تشغّل الملف
#    مباشرة (python engine/factory.py)، وده كان بيخلي `engine/copy.py` يحجب مكتبة
#    بايثون الأساسية `copy` ⇒ انهيار عند الاستيراد. بنشيل مجلد السكربت من المسار.
def _fix_path_shadow():
    import pathlib as _p, sys as _s
    here = _p.Path(__file__).resolve().parent
    _s.path[:] = [q for q in _s.path if _p.Path(q or ".").resolve() != here]


_fix_path_shadow()

QUEUE_CAP = 72                  # أقصى عدد وصفات محفوظة في الطابور
STATE = ROOT / "state"
WORK = ROOT / "work"


def _on_screen(text: str) -> str:
    """النصوص اللي بتظهر على الشاشة لازم تكون لاتينية — العربي من غير تشكيل بيطلع مشوّه."""
    t = (text or "").strip()
    if not t:
        return ""
    from engine import overlays as _ovs
    return _ovs.on_screen(t)                       # 🚫 عربي/إيموجي مُركّب مايظهرش صح على الشاشة


def _hook_text(idea: dict, gid: str, seed: int) -> str:
    """هوك صالح للعرض: نص الفكرة لو مناسب، وإلا من بنك الهوك الإنجليزي للمزاج (مش ملاحظة إنتاج)."""
    h = _on_screen(idea.get("hook"))
    if h:
        return h[:42]
    try:
        from engine import genres as _gg
        pool = (_gg.get(gid) or {}).get("hooks_en") or []
    except Exception:
        pool = []
    return (str(random.Random(seed).choice(pool))[:42] if pool else "")


# 🎴 كابشنات جاهزة للأنواع اللي ملهاش سطور مكتوبة (الميمز · ASMR · الراحة)
_DEFAULT_CARDS = {
    "funny": [("Wait for it…", 0.34), ("Follow for more", 0.80)],
    "fun_memes": [("Wait for it…", 0.34), ("Follow for more", 0.80)],
    "asmr": [("Use headphones 🎧", 0.30), ("Turn the volume up", 0.78)],
    "comfort_relax": [("Breathe in… breathe out", 0.32), ("You're doing okay", 0.80)],
    "rain_nature": [("Rain sounds for sleep", 0.30), ("Save it for tonight", 0.80)],
    "satisfying": [("Watch till the end", 0.34), ("Follow for more", 0.80)],
}


def _dur_seconds(dur, default: float = 45.0) -> float:
    """يحوّل أي صيغة مدة ("90s" · "2m" · "3h" · 90) لثواني — بلا انفجار."""
    try:
        t = str(dur or "").strip().lower()
        if not t:
            return default
        if t.endswith("h"):
            return float(t[:-1]) * 3600
        if t.endswith("m"):
            return float(t[:-1]) * 60
        if t.endswith("s"):
            return float(t[:-1])
        return float(t)
    except Exception:
        return default


# كلمات بحث بصرية دقيقة للمواضيع اللي اسمها مش بيدي صورة حلوة
QUERY_HINTS = {
    "brown noise": "cozy study room rain window night",
    "pink noise": "soft curtain light calm room",
    "white noise": "soft light curtain rain",
    "deep focus noise": "study desk lamp rain window",
    "fireplace crackling": "fireplace flames logs cozy",
    "thunderstorm at night": "thunderstorm lightning night sky",
    "rain sounds": "rain window night drops",
    "heavy rain on a window": "rain drops window glass",
    "ocean waves": "ocean waves sunset",
    "snowfall at night": "snow falling street lamp night",
    "night train ride": "train window night lights",
    "forest at night": "forest night mist trees",
    "beach at midnight": "beach night stars water",
    "lake at dusk": "lake sunset calm water",
    "wind in the pines": "pine forest mist wind",
    "mountain stream": "mountain stream rocks water",
    "quiet library": "library books warm light",
    "soft cafe ambience": "cafe window rain warm light",
    "box breathing": "calm ocean sunrise breathing",
    "4-7-8 breathing": "calm sky clouds slow",
    "before sleep": "bedroom night lamp calm",
    "two minutes of calm": "calm lake morning fog",
    "kinetic sand": "colorful kinetic sand art pastel",
    "soap cutting": "colorful soap bars texture pastel",
    "ice crushing": "ice cubes crystal light macro",
    "magnetic beads": "metal beads macro shiny",
    "water rings": "water surface ripples sunlight",
    "hydraulic press": "metal workshop sparks close up",
    "bubble wrap": "bubbles macro colorful",
    "glass and sand": "colored sand glass layers macro",
    "rolling dominoes": "colorful dominoes pattern",
    "perfect cuts": "knife cutting fruit macro colorful",
    "liquid marble pour": "paint pour swirl colorful",
    "sand raking": "sand zen garden raked lines",
    "wax seals": "wax seal colorful stamp",
    "chocolate breaking": "chocolate bar broken macro",
    "slime stretch": "colorful slime stretch macro",
    "layered resin": "resin art layers colorful",
    "ball bearings in motion": "metal ball bearings shiny macro",
    "powder pressing": "colored powder texture press",
    "paint swirl pour": "paint swirl colors macro",
    "precision slicing": "slicing vegetables macro colorful",
    "slow foam rising": "foam bubbles macro light",
    "copper and salt": "copper texture salt crystals macro",
    "ink in water": "ink in water colorful swirl",
    "dry ice fog": "dry ice fog light blue",
    "sand cutting glass": "sand texture glass macro light",
}


def _punchy(line: str, limit: int = 74) -> str:
    """يختصر الجملة الطويلة لأول جزء مفيد (نص على الشاشة لازم يبقى قصير ومقروء)."""
    s2 = " ".join(str(line or "").split())
    if len(s2) <= limit:
        return s2
    # نقطع عند أول علامة طبيعية (فاصلة · شرطة · نقطة) بعد ٣٥ حرف
    for mark in (", ", " — ", " – ", "; ", " - "):
        i = s2.find(mark, 35)
        if 0 < i <= limit:
            return s2[:i].rstrip(" ,;—-") + "."
    words, out = s2.split(), ""
    for wd in words:
        if len(out) + len(wd) + 1 > limit:
            break
        out = (out + " " + wd).strip()
    return out.rstrip(" ,;—-") + "…"


def _image_query(idea: dict) -> str:
    """كلمات بحث **بصرية** للصور: نشيل الكلمات اللي مش ليها معنى في البحث ونضيف سياق النوع."""
    q = (idea.get("image_query") or "").strip()
    if q:
        return q
    t = (idea.get("topic") or idea.get("kw") or "nature").strip()
    hint = QUERY_HINTS.get(t.lower())
    if hint:
        return hint
    t = re.sub(r"\b(sounds?|noise|ambien\w+|session|study|focus|video)\b", " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip() or "nature"
    ctx = {"sleep_ambience": "night nature calm", "focus_study": "rain window desk",
           "satisfying": "close up texture", "calm_wellness": "soft calm nature",
           "fun_memes": "funny animal", "story": "illustration",
           "facts": "", "space_nature": ""}.get(idea.get("genre") or "", "")
    words = f"{t} {ctx}".split()
    return " ".join(words[:6])            # بحث أنضف: ٦ كلمات بحد أقصى


def produce_photo_short(idea: dict, seconds: float, out_dir, seed: int,
                        force_stage: bool = False, clips_first: bool = True) -> dict:
    """فيديو من **مقاطع فيديو حقيقية متحركة** أو — لو مالقيناش — صور حقيقية.

    الأولوية: مقطع فيديو حر (Pexels · Pixabay · NASA · Wikimedia) = حركة حقيقية بلا حقوق.
    الاحتياطي: صور حقيقية بنفس محرّك الاستوديو (مفيش فشل لو مصدر وقع).
    """
    import subprocess
    from engine import proc
    gid = idea.get("genre") or "facts"
    topic = idea.get("image_query") or idea.get("topic") or idea.get("kw") or "nature"
    style = "illustration" if gid == "story" else "photo"
    min_color = 0.0 if gid in ("space_nature", "story") else 0.055    # الحقائق: صور ملوّنة حقيقية
    items, paths = photo.pick(topic, genre=gid, want=5, min_color=min_color, style=style)
    # 🎥 الفيديو الحقيقي المتحرك أولًا (بلا حقوق · بلا علامة مائية)
    clip_items, clip_paths = [], []
    if clips_first and seconds >= 12:
        try:
            from engine import clips as _clips
            clip_items = _clips.collect(topic, genre=gid, n=8)   # بنجرب اكتر ونختار الصالح
            clip_paths = []
            _rej = []
            for _it in clip_items:
                if len(clip_paths) >= 5:
                    break
                _p = _clips.download(_it)
                if _p:
                    clip_paths.append(_p)
                else:
                    _rej.append(f"{_it.get('source')}:{_it.get('rejected') or _it.get('error') or '?'}")
            # 🔎 تشخيص واضح في لوج التشغيل (نعرف منه ليه المقاطع اتستخدمت أو لأ)
            _say(f"   🎥 المقاطع الحرة: منقول {len(clip_items)} · صالح {len(clip_paths)}"
                 + (f" · مرفوض [{', '.join(_rej[:4])}]" if _rej else ""))
            if len(clip_paths) < 2:            # مش كفاية ⇒ صور حقيقية بدلًا منها
                _say(f"   ↪️ مش كفاية ({len(clip_paths)}) — صور حقيقية بدلًا منها")
                clip_paths = []
        except Exception as _ce:
            print(f"   ⚠️ مقاطع الفيديو اتعذّرت ({str(_ce)[:60]}) — صور حقيقية بدلًا منها", flush=True)
            clip_items, clip_paths = [], []
    use_clips = len(clip_paths) >= 2
    if not use_clips and not paths:
        raise RuntimeError("مفيش صور حرة متاحة للموضوع ده — نجرب غيره")
    out_dir = pathlib.Path(out_dir or (WORK / f"{date.today().isoformat()}_photo"))
    out_dir.mkdir(parents=True, exist_ok=True)
    from engine import genres as _g
    pal = _g.palette_hex(idea.get("palette"))
    _stickers, _stickers_p, _hook, _hook_p = [], [], None, None   # 🧩 متاحة في كل المسارات
    texts = []
    _HK = _hook_text(idea, gid, seed)          # 🎯 هوك صالح للعرض (مش ملاحظة إنتاج عربية)
    if _HK:
        texts.append({"at": 0.4, "dur": 2.6, "text": _HK, "pos": "lower", "size": 0.06})
    style = idea.get("montage") or ""
    lines = [ln for ln in (_punchy(x) for x in (idea.get("lines") or [])) if _on_screen(ln)][:3]
    step = max(4.0, seconds / (len(lines) + 1)) if lines else 0
    for i, ln in enumerate(lines):
        texts.append({"at": 2.6 + i * step, "dur": step * 0.88, "text": ln, "pos": "lower", "size": 0.050})
    if not lines and gid in _DEFAULT_CARDS:            # 🎴 مفيش سطور ⇒ كابشنات مزاج جاهزة
        for _t, _fr in _DEFAULT_CARDS[gid]:
            texts.append({"at": max(1.2, seconds * _fr), "dur": min(3.2, max(2.0, seconds * 0.16)),
                          "text": _t, "pos": "lower", "size": 0.048})
    if gid in ("facts", "space_nature"):
        _src = (idea.get("source") or "").replace("https://", "").replace("http://", "").replace("www.", "")
        _src = _src.split("/")[0] or "NASA / Wikimedia"       # الدومين بس — الرابط الكامل في الوصف
        texts.append({"at": max(1.0, seconds - 3.0), "dur": 3.0,
                      "text": "Source: " + _src, "pos": "lower", "size": 0.034})
    if gid == "story":                    # الحكاية بلا كلام: من غير سطور حقيقة
        texts = [tx for tx in texts if tx.get("text") == _HK]
    silent = out_dir / f"photo_{seed}.mp4"
    if use_clips:
        from engine import clips as _clips
        from engine import overlays as _ov
        # ✨ إضافات المونتاج: ملصقات متحركة + شريط تقدّم + هوك + علامة القناة + كابشنات فاخرة
        _stickers = _ov.plan_stickers(gid, seconds, seed=seed, count=3)
        _hook = _HK or None
        _texts = []
        for tx in texts:
            tx = dict(tx)
            if tx.get("text") == _hook and float(tx.get("at", 0)) < 1.0:
                continue                       # الهوك بقى بادج فوق — مش نص عائم
            tx["card"] = True                  # كارت نص فاخر بدل النص العائم
            _texts.append(tx)
        _clips.render_reel(clip_paths, silent, seconds=seconds, w=720, h=1280, fps=30, palette=pal,
                           look="cinema_cool", seed=seed, texts=_texts, stickers=_stickers,
                           progress=True, watermark="@xDaw_NoVa", hook=_hook)
    else:
        from engine import overlays as _ovp
        # ✨ دلع مسار الصور كذلك: ملصقات + هوك + كابشنات فاخرة + شريط تقدّم + علامة القناة
        _stickers_p = _ovp.plan_stickers(gid, seconds, seed=seed, count=3)
        _hook_p = _HK or None
        _texts_p = []
        for tx in texts:
            tx = dict(tx)
            if tx.get("text") == _hook_p and float(tx.get("at", 0)) < 1.0:
                continue
            tx["card"] = True
            _texts_p.append(tx)
        photo.render_reel(paths, silent, seconds=seconds, w=720, h=1280, fps=30, palette=pal,
                          look="cinema_cool", seed=seed, texts=_texts_p, stickers=_stickers_p,
                          progress=True, watermark="@xDaw_NoVa", hook=_hook_p)
    # الصوت: صوت من صنعنا + موسيقى (نفس منظومة المصنع)
    from engine import editor as _ed
    from engine import musiclib as _music
    # 🎵 موسيقى حقيقية مرخّصة (حرة للربح) — ولو مالقيناش نرجع للموسيقى المولّدة
    _track = None
    try:
        _track = _music.track_for(gid, seed=seed, seconds=seconds)
    except Exception as _me:
        print(f"   ⚠️ الموسيقى الحرة اتعذّرت ({str(_me)[:50]}) — موسيقى مولّدة", flush=True)
    if _track:
        print(f"   🎵 موسيقى: {str(_track.get('title'))[:40]} — {_track.get('license')}"
              f" ({_track.get('source')})", flush=True)
    # 🎬 مؤثرات حقيقية على لحظات المونتاج (انتقال بين المقاطع + ظهور الملصقات)
    _cues, _sfx_files = [], {}
    if use_clips and len(clip_paths) >= 2:
        _seg = max(1.2, min(seconds / float(len(clip_paths)), 7.0))
        for i in range(1, len(clip_paths)):
            _cues.append({"at": min(seconds - 0.6, i * _seg), "name": "whoosh", "gain": 0.33})
    if use_clips and (_stickers or _stickers_p):
        for sk in (_stickers or _stickers_p)[:3]:
            _cues.append({"at": float(sk["at"]), "name": "sparkle", "gain": 0.22})
    try:
        for _n in {c["name"] for c in _cues}:
            _pth = _music.sfx(_n)
            if _pth:
                _sfx_files[_n] = _pth
        if _sfx_files:
            print(f"   🎬 مؤثرات حقيقية: {', '.join(sorted(_sfx_files))}", flush=True)
    except Exception:
        _sfx_files = {}
    audio = _ed.mix_audio(seconds, [{"dur": max(1.0, seconds), "cues": _cues}] if _cues else [],
                          ambient_name=idea.get("audio"),
                          music_style=None if _track else (idea.get("music") or "dream_pulse"),
                          music_gain=(0.62 if _track else 0.5),
                          music_path=(_track or {}).get("path"), sfx_files=_sfx_files)
    wav = out_dir / f"photo_{seed}.wav"
    _ed._write_wav(wav, audio)
    _looped = False
    try:                                    # 🔁 نخلي النهاية تلاقي البداية قبل ما نركّب الصوت
        _looped = bool(_loop_glue(silent, seconds))
    except Exception:
        _looped = False
    video = out_dir / f"{gid}_{seed}.mp4"
    _vdur = proc.duration(silent) or seconds          # ⏱️ مدة الفيديو بالظبط (مش -shortest)
    subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-t", f"{_vdur:.3f}", "-movflags", "+faststart", str(video)], check=True)
    silent.unlink(missing_ok=True); wav.unlink(missing_ok=True)
    from engine import meta
    # 🌍 نسبة عربية: فيديو من كل خمسة يكون **عربي أساسي** (وعناوينه بالعربي) — والباقي إنجليزي
    #    وكل الفيديوهات بتاخد عناوين/أوصاف عربي كـlocalization وقت النشر (engine/globalize).
    _lang = "en"
    try:
        _share = float(os.environ.get("DOLLARS_AR_SHARE") or 0.2)
    except Exception:
        _share = 0.2
    if _share > 0 and random.Random(seed + 77).random() < _share:
        _lang = "ar"
    md = meta.build({**(idea.get("md_spec") or {}), **(idea.get("spec_extra") or {}), "genre": gid,
                     "pillar": g["pillar"] if (g := _g.get(gid)) else idea.get("pillar"),
                     "kind": "short", "seconds": int(seconds), "kw": idea.get("kw"),
                     "lines": lines, "source": idea.get("source"),
                     "title_style": idea.get("title_style"), "scene": idea.get("scene"),
                     # 🧠 بصمات الإنتاج — العقل بيتعلم منها إيه اللي بيجيب مشاهدات
                     "music_credit": (_track or {}).get("title"),
                     "sfx_used": sorted(_sfx_files)[:4] or None,
                     "overlays_used": bool(_stickers_p) or bool(_hook_p),
                     "real_clips": bool(use_clips)})
    md["genre"] = gid                               # 🧠 النوع يتسجل غلشان العقل يربط النوع بالمشاهدات
    md["loop_glue"] = _looped                       # 🔁 بصمة اللفّ (عشان العقل يعرف تنفع ولا لأ)
    md["hook_used"] = bool(_HK)                     # 🪝 بصمة الهوك (أول ثانية)
    md["kind"] = md.get("kind") or "short"
    if _lang == "ar":                       # 🌍 نسخة عربية أساسية (ترجمة حقيقية بالـLLM)
        try:
            from engine import globalize as _gl
            _tr = _gl.translate_fields(md["titles"][0], md["description"], ["ar"]).get("ar")
            if _tr and _tr.get("title"):
                _orig = (md["titles"][0], md["description"])
                md["titles"] = [_tr["title"]] + [t for t in md["titles"] if t != _orig[0]]
                md["description"] = _tr["description"] or _orig[1]
                md["default_language"] = "ar"
                md["localizations_en"] = {"title": _orig[0], "description": _orig[1]}
                print(f"🌍 نسخة عربية أساسية: {md['titles'][0][:48]}", flush=True)
        except Exception as _ae:
            print(f"🌍 العربي اتعذّر ({type(_ae).__name__}) — بنكمل إنجليزي", flush=True)
            md["default_language"] = "en"
    # ── 🧬 حماية من التكرار: عنوان مش مكرر خلال آخر ٣٠٠ فيديو (الخوارزمية بتعاقب التكرار) ──
    try:
        from engine import meta as _m2
        _used = _recent_titles(300)
        _alts = []
        if g:
            _ctx = {"kw": idea.get("kw") or "", "dur": f"{int(seconds)}s",
                    "hook": (g.get("hooks_en") or [""])[0], "city": idea.get("kw") or "",
                    "topic": idea.get("kw") or "", "n": 1, "place": idea.get("kw") or ""}
            for _st in (g.get("title_styles") or []):
                try:
                    _alts.append(_st.format(**_ctx))
                except Exception:
                    continue
        _before = md["titles"][0]
        _after = _m2.unique_title(_before, _used, alternatives=_alts, seed=seed)
        if _after != _before:
            md["titles"] = [_after] + [t for t in md["titles"] if t != _before]
            print(f"🧬 عنوان جديد بدل المكرر: {_after[:56]}", flush=True)
    except Exception as _de:
        print(f"🧬 فحص التكرار اتعذّر ({type(_de).__name__})", flush=True)
    # ── 🌍 نسخ عالمية لكل فيديو (localizations رسمية): يوتيوب يعرضه بلغة كل بلد ──
    try:
        _codes = [x.strip() for x in (os.environ.get("DOLLARS_LOCALES") or "ar,es,pt,hi,id").split(",") if x.strip()]
        _base = md.get("default_language") or "en"
        _need = [c for c in _codes if c != _base]
        if _need:
            from engine import globalize as _gl3
            _got = _gl3.translate_fields(md["titles"][0], md["description"], _need)
            _loc = md.setdefault("localizations", {})
            for _c, _v in (_got or {}).items():
                if isinstance(_v, dict) and _v.get("title"):
                    _loc[_c] = _v
            if _loc:
                print(f"🌍 نسخ عالمية على الفيديو: {','.join(sorted(_loc))}", flush=True)
    except Exception as _le:
        print(f"🌍 النسخ العالمية اتعذّرت ({type(_le).__name__}) — بنكمل", flush=True)
    cr = clips.credits(clip_items) if use_clips else photo.credits(items)
    _mcr = _music.credits([_track]) if _track else []
    if _mcr:
        cr = (cr or []) + _mcr
    try:
        from engine import overlays as _ov2
        cr = (cr or []) + [_ov2.EMOJI_CREDIT]      # شرط رخصة الملصقات (Twemoji CC-BY)
    except Exception:
        pass
    if cr:
        md["description"] = (md["description"] + "\n\nCredits:\n" + "\n".join(cr))[:4900]
    # 🗣️ ترجمة حقيقية على الفيديو (يوتيوب يترجمها تلقائيًا لكل اللغات)
    try:
        from engine import publish as _pb
        cue_src = [tx for tx in texts if tx.get("text") and tx.get("dur", 0) >= 1.2]
        if cue_src:
            md["captions_srt"] = _pb.build_srt(cue_src)
            md["captions_lang"] = "en"
    except Exception:
        pass
    md["sources"] = [(it.get("page") if use_clips else it.get("page")) for it in (clip_items if use_clips else items) if it.get("page")]
    md["shot_list"] = [{"scene": f"{'clip' if use_clips else 'photo'}:{it.get('source')}",
                        "dur": round(seconds / max(1, len(clip_paths if use_clips else paths)), 2),
                        "move": ("camera" if use_clips else "kenburns"), "sfx": [], "fx": []}
                       for it in (clip_items if use_clips else items)[:len(clip_paths if use_clips else paths)]]
    # 🖼️ الغلاف: من أقوى صورة + نص قصير (زي أغلفة القنوات الكبيرة)
    thumb = None
    try:
        ttexts = {
            "facts": ["3 FACTS", (idea.get("kw") or "")[:22]],
            "space_nature": [(idea.get("kw") or "").upper()[:20], f"{int(seconds)}s BLACK SCREEN"],
            "story": ["A WORDLESS STORY", (idea.get("thing") or "")[:22]],
        }.get(gid, [(idea.get("kw") or idea.get("topic") or "")[:22].upper(), f"{int(seconds)}s"])
        _tph = paths
        if use_clips:                                  # غلاف من كادر حقيقي في الفيديو
            try:
                from engine import clips as _clips
                for _cp in clip_paths:
                    _pj = _clips.poster(_cp, out_dir / f"poster_{_cp.stem}.jpg")
                    if _pj:
                        _tph = [_pj]
                        break
            except Exception:
                _tph = paths
        thumb = photo.thumb_from_photo(_tph, ttexts, out_dir / f"{gid}_{seed}_thumb.jpg", palette=pal)
    except Exception:
        thumb = None
    return {"kind": ("clip_short" if use_clips else "photo_short"), "video": str(video), "meta": md,
            "pillar": md.get("pillar"), "thumbnail": str(thumb) if thumb else None,
            "duration": f"{int(seconds)}s", "scene": f"{'clip' if use_clips else 'photo'}:{topic}",
            "audio": idea.get("audio"), "palette": idea.get("palette"), "genre": gid,
            "photos": len(paths), "clips": len(clip_paths), "real_clips": bool(use_clips),
            "music": _music.license_line(_track), "credits": cr,
            "music_needs_credit": bool(_track and _track.get("needs_credit"))}


def _say(text: str) -> None:
    """بث حي: السجل العادي + Issue «سجل المصنع». أي فشل هنا مايوقفش الشغل."""
    print(text, flush=True)
    try:
        from engine import live
        live.say(text, file=False)
    except Exception:
        pass


def _jload(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def _jdump(p, obj):
    p = pathlib.Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _load_ledger() -> dict:
    return _jload(STATE / "produced.json", {"done": [], "stats": {}, "created": None}) or {"done": []}


def _save_ledger(led: dict):
    led["updated"] = datetime.now(timezone.utc).isoformat()
    _jdump(STATE / "produced.json", led)


def _plan(date_str: str | None = None) -> dict:
    """خطة اليوم من العقل (أو بيولّدها لو مش موجودة)."""
    date_str = date_str or date.today().isoformat()
    p = STATE / f"plan_{date_str}.json"
    plan = _jload(p)
    if not plan:
        try:                                  # استوديو الأنواع (٨ أنواع متنوّعة + حارس التنوّع)
            from engine import studio as _studio
            plan = _studio.build_day(date_str, state_dir=STATE)
        except Exception as _e:
            brain = agent.Brain.load()
            plan = agent.plan_day(brain, date_str, characters=agent.load_characters().get("characters"))
            brain.save()
    # 🚦 الإيقاع: الأدوار بتتقلّم لسقف الساعة (افتراضي ١ في الساعة = ٢٤ فيديو/يوم).
    #    الخطة قبل كده كانت ٨ في الساعة ⇒ أي تعويض بيعمل دفعة كبيرة، ويوتيوب بيقراها سبام.
    try:
        _rate = max(1, int(os.environ.get("DOLLARS_SLOTS_PER_HOUR") or 1))
        slots = plan.get("slots") or []
        per_hour: dict[tuple, int] = {}
        kept = []
        for sl in slots:
            key = (sl.get("kind"), int(sl.get("hour", 0)))
            n = per_hour.get(key, 0)
            if sl.get("kind") == "short" and n >= _rate:
                continue
            per_hour[key] = n + 1
            kept.append(sl)
        if kept and len(kept) != len(slots):
            plan = dict(plan, slots=kept)
    except Exception:
        pass
    return plan


def next_slots(kind: str = "short", count: int = 1, date_str: str | None = None) -> list:
    """أدوار لسه ما اتعملتش من خطة اليوم (شورت / طويل)."""
    plan = _plan(date_str)
    led = _load_ledger()
    done = {(d.get("date"), d.get("hour"), d.get("kind")) for d in led.get("done", [])}
    out = []
    _now = datetime.now(timezone.utc)
    for s in plan.get("slots", []):
        if s.get("kind") != kind:
            continue
        if (plan["date"], s["hour"], kind) in done:
            continue
        # ⏰ مش بناخد دور ساعته لسه مجتش: الأدوار بتستهلك بالساعة الحقيقية بس
        #    (قبل كده الدفعات كانت بتاكل أدوار المستقبل ⇒ النشر يقف ساعتها فجأة)
        if str(plan.get("date")) == _now.date().isoformat() and int(s.get("hour", 0)) > _now.hour:
            continue
        out.append(dict(s, date=plan["date"]))
        if len(out) >= count:
            break
    return out


def missed_slots(kind: str = "short", now=None) -> int:
    """كام دور فات في خطة النهاردة ولسه ما اتعملش (عشان الساعة لو اتأخرت ما تضيّعش حاجة)."""
    now = now or datetime.now(timezone.utc)
    plan = _plan()
    led = _load_ledger()
    done = {(d.get("date"), d.get("hour"), d.get("kind")) for d in led.get("done", [])}
    n = 0
    for sl in plan.get("slots", []):
        if sl.get("kind") != kind:
            continue
        if (plan["date"], sl["hour"], kind) in done:
            continue
        if int(sl.get("hour", 0)) <= now.hour or plan.get("date", "") < now.date().isoformat():
            n += 1
    return n


def produce(slot: dict, out_dir=None, seed: int | None = None) -> dict:
    """
    يطلّع الفيديو المطلوب حسب النوع: شورت مريح · أجواء · قصة · نوم طويل.
    """
    idea = slot.get("idea") or {}
    pillar = idea.get("pillar") or "satisfying"
    dur = idea.get("duration") or ""
    seed = seed if seed is not None else random.Random(f"{slot.get('date')}|{slot.get('hour')}").randint(1, 10**6)
    out_dir = pathlib.Path(out_dir or (WORK / f"{slot.get('date')}_{slot.get('hour'):02d}"))
    out_dir.mkdir(parents=True, exist_ok=True)
    ed = editor.Editor(str(out_dir), seed=seed)
    # المرجع البصري (Pinterest/Openverse) بيحدّد المظهر والكاميرا والمشاهد — والموسيقى من صنعنا
    try:
        from engine import refs as refs_mod
        recipe = refs_mod.recipe_for(pillar)
    except Exception:
        recipe = {}
    style_kw = {k: recipe[k] for k in ("look", "moves", "scenes", "music", "palette") if recipe.get(k)}
    # ♾️ المخزون اللانهائي: كل فيديو بياخد تركيبة جديدة (حركة · انتقال · لوحة · مشهد إضافي · نمط موسيقى)
    try:
        from engine import unlimited as uq
        style_kw = uq.enrich(style_kw, pillar, advance=(slot.get("force") is not True))
    except Exception as _e:
        uq = None
        recipe["unlimited"] = None
    if slot.get("kind") == "long":         # الطويلة: المشهد هو اللي يحكم المظهر (اللوحة والحركة بتفضل)
        style_kw.pop("look", None); style_kw.pop("scenes", None)
    # عبارات بحث حقيقية (بلا مفتاح) للتخصص — بتدخل الوسوم والوصف
    try:
        pillar_key = {"sleep": "sleep", "focus": "focus", "satisfying": "satisfying", "story": "story"}.get(pillar, "satisfying")
        style_kw["phrases"] = refs_mod.phrases_for(pillar_key)
    except Exception:
        pass
    # 🔎 العنوان من طلب حقيقي (أوتوكومبليت بحث يوتيوب): بناخد العبارة اللي الناس بتكتبها فعلًا
    #    — ده اللي بيخلي الفيديو يطلع في نتائج البحث بدل ما يتألف من دماغنا.
    if (os.environ.get("DOLLARS_DEMAND") or "1").strip() not in ("0", "false", "no"):
        try:
            from engine import demand as _dmd
            _g = idea.get("genre") or pillar
            _seen = [str(t) for t in _recent_titles(120)]
            _seen += [str(x.get("kw") or "") for x in _seen]
            _ph = _dmd.pick(_g, rnd=random.Random(seed + 909), used=_seen)
            if _ph:
                idea = dict(idea)
                idea["kw"] = _dmd.title_from_phrase(_ph)
                idea["demand_phrase"] = _ph
                print(f"🔎 عبارة عليها طلب حقيقي: {_ph}", flush=True)
        except Exception as _dme:
            print(f"🔎 محرّك الطلب اتعذّر ({type(_dme).__name__}) — بنكمل", flush=True)
    if not str(idea.get("kw") or "").strip():              # 🛡️ مفيش كلمة مفتاحية ⇒ عنوان مكسور (كان بيطلع «— ...»)
        _gname = str(idea.get("genre") or pillar or "nature").replace("_", " ").title()
        idea = dict(idea)
        try:
            from engine import demand as _dmf
            _pf = _dmf.pick(idea.get("genre") or pillar, rnd=random.Random(seed + 313))
            idea["kw"] = _dmf.title_from_phrase(_pf) if _pf else _gname
        except Exception:
            idea["kw"] = _gname
        print(f"🛡️ عنوان من غير كلمة مفتاحية ⇒ استخدمنا: {idea['kw']}", flush=True)
    t0 = time.time()

    # ── الاستوديو: النوع بيحدّد المشهد والصوت واللوحة والانتقال + النص على الشاشة ──
    gid = idea.get("genre")
    gspec: dict = {}
    if gid:
        style_kw.update({k: idea[k] for k in ("scene", "audio", "palette", "transition")
                         if idea.get(k)})
        style_kw["scenes"] = [idea["scene"]]
        text_policy = None
        try:
            from engine import genres as _g
            text_policy = _g.get(gid).get("text_policy")
        except Exception:
            pass
        texts = []
        if idea.get("hook"):
            texts.append({"at": 0.4, "dur": 2.6, "text": idea["hook"], "pos": "lower", "size": 0.06})
        if text_policy == "en_lines" and idea.get("lines"):
            step = max(4.0, _dur_seconds(idea.get("duration"), 45.0) / (len(idea["lines"]) + 1))
            for i, ln in enumerate(idea["lines"][:3]):
                texts.append({"at": 3.0 + i * step, "dur": step * 0.9, "text": ln, "pos": "lower", "size": 0.05})
        if text_policy == "en_lines_label":
            texts.append({"at": 2.0, "dur": 3.0, "text": "Imagery: NASA / Wikimedia (public sources)",
                          "pos": "lower", "size": 0.038})
        if texts:
            style_kw["texts"] = texts
        gspec = {k: idea[k] for k in ("genre", "kw", "topic", "lines", "source", "playlist",
                                      "hook", "character", "thing") if idea.get(k)}
        gspec["title_style"] = idea.get("title_style")
    # 🖼️ الأساس بقى **صور حقيقية** لكل الشورتس (ناسا · ويكيميديا · بيكسابي · بيكسلز)
    #    ولو مالقيناش صور للموضوع، بنرجع تلقائيًا للمشاهد المولّدة (مفيش فشل).
    photo_rec = None
    if slot.get("kind") == "short" and pillar != "story":
        try:
            _idea = dict(idea)
            _idea["genre"] = gid or {"focus": "focus_study", "sleep": "sleep_ambience"}.get(pillar, "satisfying")
            _idea["image_query"] = _image_query(_idea)
            _idea.setdefault("spec_extra", gspec)
            photo_rec = produce_photo_short(_idea, _dur_seconds(dur, 30.0), out_dir, seed)
        except Exception as _pe:
            _say(f"   ⚠️ مفيش صور حقيقية ({str(_pe)[:70]}) — مشهد مولّد بدلًا منها")
            photo_rec = None

    if photo_rec is not None:
        rec = photo_rec
        rec.update(pillar=("focus" if pillar == "focus" else "sleep" if pillar == "sleep" else "satisfying"),
                   duration=dur)
    elif slot.get("kind") == "long" and pillar in ("sleep", "focus"):
        for k in ("scene", "audio", "scenes"):        # الطويلة بتاخد المشهد والصوت ببارامتراتها
            style_kw.pop(k, None)
        hours = float(str(dur).replace("h", "") or 10)
        hours = hours if hours in (3, 8, 10, 2, 4, 6, 12) else 8
        scene = idea.get("scene") or "valley_lake"
        audio = random.Random(seed).choice(["calm_night", "sleep_rain", "ocean", "fireplace", "focus"])
        # 🎥 مقاطع فيديو حقيقية للطويلة — **مقفولة دلوقتي** لحد ما نتأكد من الشورتس.
        #    للتفعيل: DOLLARS_LONG_CLIPS=1 (الافتراضي: الصور المعتمدة · سلوك مستقر)
        import os as _os
        long_videos = []
        _long_clips_on = str(_os.environ.get("DOLLARS_LONG_CLIPS", "")).strip().lower() in ("1", "true", "yes", "on")
        if scene != "black_screen" and _long_clips_on:
            try:
                _vq = _image_query({"genre": ("focus_study" if pillar == "focus" else "sleep_ambience"),
                                    "kw": idea.get("kw") or idea.get("topic") or "nature"})
                _vi = clips.collect(_vq, genre=("focus_study" if pillar == "focus" else "sleep_ambience"),
                                    n=6)
                for _it in _vi:
                    if len(long_videos) >= 5:
                        break
                    _p = clips.download(_it)
                    if _p:
                        long_videos.append(_p)
            except Exception as _ve:
                _say(f"   ⚠️ مقاطع الطويلة اتعذّرت ({str(_ve)[:60]}) — صور بدلًا منها")
                long_videos = []
        # 🖼️ البديل: صور حقيقية (حركة هادية · بلا نصوص · حلقة ٦٠ ثانية)
        longs_photos = []
        if scene != "black_screen" and not long_videos:
            try:
                _qi = _image_query({"genre": ("focus_study" if pillar == "focus" else "sleep_ambience"),
                                    "kw": idea.get("kw") or idea.get("topic") or "nature"})
                _n = 8 if pillar == "focus" else 6
                _its, longs_photos = photo.pick(_qi, genre="sleep_ambience", want=_n, min_color=0.012)
            except Exception as _le:
                _say(f"   ⚠️ صور الطويلة اتعذّرت ({str(_le)[:60]})")
                longs_photos = []
        rec = ed.make("sleep_long", hours=hours, scene=scene, audio=audio,
                      videos=long_videos or None, photos=longs_photos[:8] or None, **style_kw)
        rec.update(pillar="sleep", duration=f"{int(hours)}h")
    elif pillar == "story":
        rec = ed.make("story_short", seconds=max(20.0, min(_dur_seconds(dur, 60.0), 120.0)),
                      spec_extra=gspec, **{k: v for k, v in style_kw.items() if k in ("palette", "transition", "audio")})
        rec.update(pillar="story", duration=dur)
    elif pillar in ("focus", "sleep") or (slot.get("kind") == "short" and random.Random(seed).random() < 0.25):
        rec = ed.make("ambience_short", seconds=_dur_seconds(dur, 45.0),
                      meta_pillar=("focus" if pillar == "focus" else "sleep"),
                      spec_extra=gspec, **style_kw)
        rec.update(pillar=("focus" if pillar == "focus" else "sleep"), duration=dur)
    else:
        secs = _dur_seconds(dur, 30.0)
        rec = ed.make("satisfying_short", seconds=secs if 15 <= secs <= 60 else 30,
                      spec_extra=gspec, **style_kw)
        rec.update(pillar="satisfying", duration=dur)

    rec["recipe"] = {k: recipe.get(k) for k in
                     ("look", "moves", "scenes", "music", "mood", "matched", "palette", "palette_source")} if recipe else None
    if style_kw.get("unlimited"):
        rec["unlimited"] = style_kw["unlimited"]          # رقم التركيبة من المخزون اللانهائي
    rec["slot"] = slot
    if idea.get("sig"):
        try:
            from engine import variety as _v
            ttl = ((rec.get("meta") or {}).get("titles") or [""])[0]
            sg = dict(idea["sig"]); sg["title_shape"] = _v._shape(ttl)
            _v.record(sg)
            rec["variety"] = sg
        except Exception:
            pass
    rec["seconds_spent"] = round(time.time() - t0, 1)
    rec["seed"] = seed
    rec["produced_at"] = datetime.now(timezone.utc).isoformat()
    return rec


QUOTA_WORDS = ("quota", "exceeded", "rateLimit", "dailyLimit", "uploadLimit", "too many requests")


def rate_gate() -> dict:
    """⏳ بوابة الإيقاع: «مفيش نشر لو فيه فيديو نزل قريب» — إيقاع ساعة/ساعة بالظبط.

    المشكلة اللي بتحلها: أكتر من workflow بيقدر ينشر (الوردية + تفريغ الطابور + النبضة
    الساعية)، فالقناة كانت بتاخد دفعات. البوابة بتخلي **أي** مصدر يلتزم بنفس الإيقاع.

        DOLLARS_GATE_MIN = ٤٠ دقيقة (افتراضي) · DOLLARS_GATE_MIN=0 يوقف البوابة
    """
    try:
        _min = float(os.environ.get("DOLLARS_GATE_MIN") or 40)
    except Exception:
        _min = 40.0
    if _min <= 0:
        return {"ok": True, "reason": "البوابة مقفولة"}
    try:
        pub = (_jload(STATE / "published.json", {}) or {}).get("videos", []) or []
        times = []
        for v in pub:
            try:
                times.append(datetime.fromisoformat(str(v.get("published_at")).replace("Z", "+00:00")))
            except Exception:
                continue
        if not times:
            return {"ok": True, "reason": "مفيش نشر قبل كده"}
        last = max(times)
        mins = (datetime.now(timezone.utc) - last).total_seconds() / 60.0
        if mins < _min:
            return {"ok": False, "reason": f"آخر فيديو نزل قبل {mins:.0f} دقيقة (أقل من {_min:.0f}) — "
                                           f"بنحافظ على إيقاع ساعة/ساعة", "minutes": mins}
        return {"ok": True, "reason": f"آخر نشر قبل {mins:.0f} دقيقة"}
    except Exception as e:
        return {"ok": True, "reason": f"البوابة اتعذّرت ({type(e).__name__}) — بنكمل"}


def soft_capacity() -> int:
    """كام رفعة نقدر نجرّبها دلوقتي. في الوضع المرن: بنجرّب ونسيب يوتيوب هو اللي يقول لأ."""
    try:
        from engine import publish as _pb
        if getattr(_pb, "SOFT_QUOTA", False):
            return max(1, _pb.extra_capacity())          # سقف مرن — مش بيمنع الوردية
        return _pb.remaining_capacity()
    except Exception:
        return 1


def quota_exhausted(res: dict) -> bool:
    """هل الفشل سببه كوتة يوتيوب؟ (وقتها بنوقف بدل ما نرندر حاجات مش هتنشر)"""
    if not res or res.get("published"):
        return False
    txt = str(res.get("reason") or "").lower()
    return any(w.lower() in txt for w in QUOTA_WORDS)


def publish_or_stage(rec: dict, force_stage: bool = False) -> dict:
    """
    ينشر لو القناة مربوطة، وإلا يحفظ في الطابور. بيرجّع سطر النتيجة.
    """
    md = rec.get("meta") or {}
    video = rec.get("video")
    if not video or not pathlib.Path(video).exists():
        return {"published": False, "reason": "مفيش فيديو"}

    if md:
        problems = meta.validate(md)
        serious = [p for p in problems if "إفصاح" in p or "كلمات" in p or "مصنوع للأطفال" in p]
        if serious:
            return {"published": False, "reason": f"الفحص رفض النشر: {serious}"}

    # 🩺 الفحص الطبي للفيديو: **بيتحذّر مش بيمنع** — الاستثناء الوحيد: ملف تالف
    quality_block = None
    try:
        from engine import quality
        passed, qrep = quality.gate(video, kind=("long" if rec.get("kind") == "long" else "short"),
                                    seconds=None)
        warn = qrep.get("warnings") or []
        rec["quality"] = {"pass": passed, "warnings": warn, "fatal": qrep.get("fatal") or []}
        if not passed:
            quality_block = f"🚦 الفيديو تالف — مايتنشرش: {qrep.get('fatal') or qrep.get('error')}"
            _say(f"   {quality_block}")
        elif warn:
            _say(f"   🩺 ملاحظات جودة (بتنشر عادي): {warn}")
    except Exception as _e:
        rec["quality"] = {"pass": None, "error": str(_e)[:120]}

    if quality_block:
        ok = {"ok": False, "reason": quality_block}
    else:
        ok = publish.available()
    if ok["ok"] and not force_stage:
        try:
            res = publish.publish(video, md, thumb_path=rec.get("thumbnail"))
            return {"published": True, "video_id": res.get("id"), "url": res.get("url"),
                    "thumbnail": res.get("thumbnail"), "playlist": res.get("playlist")}
        except Exception as e:
            return {"published": False, "reason": f"الرفع فشل: {type(e).__name__}: {e}"}
    q = _jload(STATE / "queue.json", {"items": []}) or {"items": []}
    q["items"].append({
        "at": datetime.now(timezone.utc).isoformat(),
        "slot": rec.get("slot"), "seed": rec.get("seed"), "kind": rec.get("kind"),
        "title": (md.get("titles") or [pathlib.Path(video).stem])[0],
        "pillar": rec.get("pillar"), "duration": rec.get("duration"),
        "reason": ok["reason"] if not ok["ok"] else "تم التخطّي بأمر",
        "quality": rec.get("quality"),
    })
    _jdump(STATE / "queue.json", q)
    return {"published": False, "staged": True, "reason": ok["reason"],
            "queue_length": len(q["items"])}


def render_queue(force_stage: bool = False, limit: int | None = None, out_dir=None) -> dict:
    """
    يعيد إنتاج كل حاجة في الطابور **بنفس الوصفة والبذرة** (نفس الفيديو بالظبط) وينشرها.
    مهيّأ لليوم اللي نربط فيه القناة: أمر واحد يحوّل الطابور لمحتوى منشور.
    """
    q = _jload(STATE / "queue.json", {"items": []}) or {"items": []}
    # 🎯 أولوية الشورتس: الشورتس هي الأساس (طلب المستخدم) — والطويلة تفضل في الطابور بأمان
    #    لحد ما نقول ننشرها (مفيش حذف ولا فقدان لأي حاجة).
    _kinds = [k.strip() for k in (os.environ.get("DOLLARS_DRAIN_KINDS") or "short").split(",") if k.strip()]
    def _kind_of(x):
        return ((x.get("slot") or {}).get("kind") or "short")
    short_first = [x for x in q["items"] if _kind_of(x) in _kinds]
    rest = [x for x in q["items"] if _kind_of(x) not in _kinds]
    _pool = short_first + rest if _kinds else list(q["items"])
    if _kinds and rest:
        _say(f"⏳ {len(rest)} عنصر طويل مستني في الطابور (مش بيتنشر دلوقتي — الشورتس لها الأولوية)")
    items = _pool[:limit] if limit else list(_pool)
    lines, done = [], 0
    try:                                     # نسأل قبل ما نصرف ٥ دقايق رندر على الفاضي
        left = soft_capacity()
        if publish.usable_projects() and left <= 0:
            _say("⛔ الحصة اليومية خلصت على كل المشاريع — مش بنرندر عشان ما نضيّعش وقت. "
                 "الطابور زي ما هو وهينزل لوحده أول ما الحصة ترجع.")
            return {"processed": 0, "remaining": len(items), "lines": ["⛔ الحصة خلصت"], "stopped": "quota"}
        _say(f"♻️ تفريغ الطابور: {len(items)} عنصر · سعة النشر المتبقية النهاردة: {left} رفعة")
    except Exception:
        pass
    _gate = rate_gate()                      # ⏳ نفس الإيقاع على تفريغ الطابور كذلك
    if not _gate.get("ok"):
        _say(f"⏳ تفريغ الطابور مستني الإيقاع: {_gate['reason']}")
        return {"processed": 0, "remaining": len(q["items"]), "lines": [_gate["reason"]], "stopped": "gate"}
    _say(f"♻️ تفريغ الطابور: {len(items)} عنصر · رندر + نشر عنصر عنصر")
    order = sorted(range(len(items)),
                   key=lambda j: (0 if (items[j].get("slot") or {}).get("kind") == "short" else 1, j))
    items = [items[j] for j in order]                      # ⚡ الشورتس (أسرع) الأول
    q["items"] = items
    for n, it in enumerate(items, 1):
        slot = it.get("slot")
        if not slot:                                        # 📦 وصفة ناقصة ⇒ أرشيف (مش حذف)
            _say(f"[{n}/{len(items)}] 📦 «{it.get('title')}» من غير وصفة — اتنقل لأرشيف الطابور")
            sk = _jload(STATE / "queue_skipped.json", {"items": []}) or {"items": []}
            sk["items"].append({**it, "skipped_at": datetime.now(timezone.utc).isoformat(),
                                "reason": "وصفة ناقصة (من غير slot)"})
            _jdump(STATE / "queue_skipped.json", sk)
            q["items"] = [x for x in q["items"] if x is not it]
            continue
        it["tries"] = int(it.get("tries") or 0) + 1
        if it["tries"] > 3:                                 # 🔁 حد منطقي: بعد 3 محاولات نأرشفة (مش حذف)
            _say(f"[{n}/{len(items)}] 📦 «{it.get('title')}» فشل 3 مرات — اتنقل لأرشيف الطابور")
            sk = _jload(STATE / "queue_skipped.json", {"items": []}) or {"items": []}
            sk["items"].append({**it, "skipped_at": datetime.now(timezone.utc).isoformat(),
                                "reason": it.get("last_reason") or "فشل متكرر"})
            _jdump(STATE / "queue_skipped.json", sk)
            continue
        try:
            if publish.usable_projects() and soft_capacity() <= 0:
                _say("⛔ الحصة خلصت — وقفنا قبل الرندر (مبنضيّعش وقت) والباقي هينزل لوحده.")
                _jdump(STATE / "queue.json", q)
                _log(lines + ["⛔ الحصة خلصت أثناء الدفعة"])
                return {"processed": done, "remaining": len(q["items"]), "lines": lines, "stopped": "quota"}
            _say(f"[{n}/{len(items)}] 🎬 بنرندر: {it.get('title')}")
            t0 = time.time()
            rec = produce(slot, out_dir=out_dir, seed=it.get("seed"))
            _say(f"[{n}/{len(items)}] ✅ الرندر خلص في {time.time() - t0:.0f} ثانية — بنرفع على يوتيوب")
            res = publish_or_stage(rec, force_stage=force_stage)
            if res.get("published"):
                _say(f"[{n}/{len(items)}] 🎉 اتنشر: {res.get('url')}")
            else:
                _say(f"[{n}/{len(items)}] ⏸️ محصلش نشر: {res.get('reason')}")
            record(rec, res)
            done += 1
            lines.append(f"↻ {it.get('title')} → " + (f"نُشر {res.get('url')}" if res.get("published") else f"لسه في الطابور ({res.get('reason')})"))
            it["last_reason"] = res.get("reason")
            if res.get("published") and not force_stage:
                q["items"] = [x for x in q["items"] if x is not it]
            elif quota_exhausted(res):
                lines.append("⛔ كوتة يوتيوب خلصت — وقفنا بدل ما نضيّع وقت. الباقي هينزل لوحده (كل ساعة).")
                _jdump(STATE / "queue.json", q)
                _log(lines)
                return {"processed": done, "remaining": len(q["items"]), "lines": lines, "stopped": "quota"}
        except Exception as e:
            _say(f"[{n}/{len(items)}] ❌ خطأ: {type(e).__name__}: {str(e)[:300]}")
            it["last_reason"] = f"{type(e).__name__}: {str(e)[:120]}"
            lines.append(f"❌ فشل إعادة إنتاج «{it.get('title')}»: {type(e).__name__}: {e}")
    _jdump(STATE / "queue.json", q)
    _log(lines or ["الطابور فاضي — مفيش حاجة تعاد"])
    return {"processed": done, "remaining": len(q["items"]), "lines": lines}


def record(rec: dict, result: dict):
    led = _load_ledger()
    led.setdefault("done", []).append({
        "date": rec.get("slot", {}).get("date"), "hour": rec.get("slot", {}).get("hour"),
        "kind": rec.get("slot", {}).get("kind"), "pillar": rec.get("pillar"),
        "duration": rec.get("duration"), "scene": rec.get("scene"),
        "video": rec.get("video"), "title": ((rec.get("meta") or {}).get("titles") or [""])[0],
        "published": bool(result.get("published")), "url": result.get("url"),
        "reason": result.get("reason"), "seconds_spent": rec.get("seconds_spent"),
        "at": rec.get("produced_at"),
    })
    st = led.setdefault("stats", {})
    st["total"] = st.get("total", 0) + 1
    st["published"] = st.get("published", 0) + (1 if result.get("published") else 0)
    st["staged"] = st.get("staged", 0) + (1 if result.get("staged") else 0)
    st["by_pillar"] = st.get("by_pillar", {})
    st["by_pillar"][rec.get("pillar", "?")] = st["by_pillar"].get(rec.get("pillar", "?"), 0) + 1
    _save_ledger(led)
    return led


def _log(lines: list):
    p = STATE / "factory_log.md"
    old = p.read_text(encoding="utf-8") if p.exists() else "# 🏭 سجل المصنع\n"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    p.write_text(old.rstrip() + f"\n\n## {stamp}\n" + "\n".join(f"- {l}" for l in lines) + "\n",
                encoding="utf-8")


def run(kind: str = "short", count: int = 1, force_stage: bool = False, out_dir=None,
        catchup: bool = False, max_catchup: int | None = None) -> dict:
    if catchup:
        miss = missed_slots(kind)
        # 🚦 سقف التعويض: دفعة واحدة في المرة (بدل ٤). الدفع الجماعي (٥٢ فيديو في ساعة مرة)
        #    كان بيبان لليوتيوب «سبام» وبيدفن القناة ⇒ صفر مشاهدات. الوردية الساعية بتعوّض الباقي بهدوء.
        try:
            _cap = int(os.environ.get("DOLLARS_CATCHUP_MAX") or 1)
        except Exception:
            _cap = 1
        if max_catchup is not None:
            _cap = max_catchup
        count = max(count, min(max(1, _cap), miss)) if kind == "short" else max(count, min(1, miss))
    _gate = rate_gate()                      # ⏳ إيقاع ساعة/ساعة (ولا دفعات)
    if not _gate.get("ok"):
        msg = f"⏳ مستنيين الإيقاع: {_gate['reason']}"
        _say(msg)
        _log([msg])
        return {"slots": 0, "results": [], "lines": [msg], "stopped": "gate"}
    # ⛔ وعي بالحصة: مش بنرندر حاجة مش هينفع تنشر (الوقت أغلى من الرندر)
    try:
        from engine import publish as _pb
        if _pb.usable_projects():
            left = soft_capacity()
            if left <= 0:
                msg = (f"⛔ الحصة اليومية خلصت على كل المشاريع — وقفنا قبل الرندر. "
                       f"الطابور هينزل لوحده أول ما الحصة ترجع (07:02 و 07:32).")
                _say(msg)
                _log([msg])
                return {"slots": 0, "results": [], "lines": [msg], "stopped": "quota"}
            if kind == "short" and left < count:
                lines_pre = [f"ℹ️ سعة النشر المتبقية {left} رفعة ⇒ هننتج {left} بس بدل {count}"]
                count = left
                _say(lines_pre[0])
    except Exception:
        lines_pre = []
    slots = next_slots(kind, count)
    lines, results = list(locals().get("lines_pre") or []), []
    if catchup and count > 1:
        lines.append(f"⏱️ تعويض: النهاردة فيه {count} دور مستحق ⇒ بنطلّعهم كلهم")
    if not slots:
        lines.append(f"مفيش أدوار {kind} فاضلة في خطة النهاردة — العقل هيعمل خطة بكرة")
    for slot in slots:
        try:
            rec = produce(slot, out_dir=out_dir)
            res = publish_or_stage(rec, force_stage=force_stage)
            led = record(rec, res)
            results.append({"slot": f"{slot['date']} {slot['hour']:02d}:00", "pillar": rec.get("pillar"),
                            "duration": rec.get("duration"), "video": rec.get("video"),
                            "result": res, "total_done": led["stats"]["total"]})
            lines.append(f"{slot['date']} {slot['hour']:02d}:00 · {rec.get('pillar')} · "
                         f"{rec.get('duration')} · {pathlib.Path(str(rec.get('video'))).name} · "
                         + (f"نُشر: {res.get('url')}" if res.get("published") else f"في الطابور ({res.get('reason')})"))
        except Exception as e:
            lines.append(f"❌ {slot.get('date')} {slot.get('hour')}:00 — فشل: {type(e).__name__}: {e}")
            traceback.print_exc()
    _log(lines)
    return {"slots": len(slots), "results": results, "lines": lines}


def status() -> dict:
    led = _load_ledger()
    q = _jload(STATE / "queue.json", {"items": []}) or {"items": []}
    pub = publish.available()
    plan = _plan()
    done_today = [d for d in led.get("done", []) if d.get("date") == date.today().isoformat()]
    return {
        "plan_for": plan.get("date"), "planned_slots": len(plan.get("slots", [])),
        "done_total": led.get("stats", {}).get("total", 0),
        "published_total": led.get("stats", {}).get("published", 0),
        "staged_total": led.get("stats", {}).get("staged", 0),
        "done_today": len(done_today),
        "queue": len(q["items"]),
        "publishing": pub["reason"],
        "by_pillar": led.get("stats", {}).get("by_pillar", {}),
        "last": (led.get("done") or [{}])[-1],
    }


def report_text() -> str:
    s = status()
    lines = [
        "# 🏭 حالة المصنع — Dollars Studio", "",
        f"- خطة اليوم: **{s['planned_slots']}** دور · اتعمل النهاردة: **{s['done_today']}**",
        f"- الإجمالي: **{s['done_total']}** فيديو (منهم **{s['published_total']}** منشور · "
        f"**{s['staged_total']}** في الطابور)",
        f"- الطابور الجاهز للنشر: **{s['queue']}**",
        f"- النشر: {s['publishing']}",
        f"- التوزيع: {s['by_pillar'] or '—'}",
    ]
    if s.get("last"):
        lines.append(f"- آخر حاجة: {s['last'].get('title')} ({s['last'].get('pillar')})")
    return "\n".join(lines)


def _loop_glue(path, seconds: float, blend: float = 0.4) -> bool:
    """🔁 يخلّي الفيديو يلفّ على نفسه: آخر ٠٫٤ ثانية بتتلاقى مع أول ٠٫٤ ثانية.

    ليه ده مهم؟ إعادة المشاهدة (rewatch) أقوى إشارة في ترتيب الشورتس — ولما نهاية
    الفيديو تبقى نفس بدايته، العين مش بتحس بالقطع فبيرجع من أول تاني.
    المدة مابتتغيّرش (بنقطع نفس الجزء ونستبدله بالمزج).
    """
    if (os.environ.get("DOLLARS_LOOP") or "1").strip() in ("0", "false", "no"):
        return False
    path = pathlib.Path(path)
    if seconds < 4 or not path.exists():
        return False
    out = path.with_name(path.stem + "_loop.mp4")
    b = max(0.25, min(float(blend), seconds / 4.0))
    end = max(b + 0.05, seconds - b)
    fc = (f"[0:v]trim=start={end:.3f},setpts=PTS-STARTPTS,fps=30[a];"
          f"[0:v]trim=start=0:end={b:.3f},setpts=PTS-STARTPTS,fps=30[b];"
          f"[a][b]xfade=transition=fade:duration={b:.3f}:offset=0,format=yuv420p[ab];"
          f"[0:v]trim=start=0:end={end:.3f},setpts=PTS-STARTPTS,fps=30[c];"
          f"[c][ab]concat=n=2:v=1:a=0[v]")
    import subprocess
    from engine import proc as _proc
    cmd = [_proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
           "-filter_complex", fc, "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    try:
        subprocess.run(cmd, check=True, timeout=300)
        if out.exists() and out.stat().st_size > 10_000:
            out.replace(path)
            print("🔁 خاتمة بتلفّ على البداية (إعادة مشاهدة)", flush=True)
            return True
    except Exception as e:
        print(f"🔁 اللفّ اتعذّر ({type(e).__name__}) — بنكمل بالفيديو الأصلي", flush=True)
    out.unlink(missing_ok=True)
    return False


def _sync_state(tag: str = "") -> None:
    """☁️ يحفظ سجل النشر في جيت هوب بعد كل دورة (لو DOLLARS_SYNC=1).

    السبب: قبل كده الحالة كانت بتترفع بعد الوردية كلها ⇒ التقارير/الفحص كانوا
    بيشوفوا فيديوهات قديمة، ومنع التكرار ماكانش عارف آخر اللي اتنشر في وردية تانية.
    """
    if (os.environ.get("DOLLARS_SYNC") or "").strip() not in ("1", "true", "yes"):
        return
    import subprocess
    def g(*a, **kw):
        return subprocess.run(["git", *a], capture_output=True, text=True, timeout=180, **kw)
    try:
        g("add", "state")
        if g("diff", "--cached", "--quiet").returncode == 0:
            print("☁️ مفيش تغيير في السجل — مفيش رفع", flush=True)
            return
        g("commit", "-qm", f"🔁 دورة {tag}: سجل وطابور", "-c", "user.name=Dollars Factory",
          "-c", "user.email=factory@dawshax.local")
        g("fetch", "-q", "origin", "main")
        if g("pull", "--rebase", "--autostash", "origin", "main").returncode != 0:
            g("rebase", "--abort")
            g("merge", "-X", "ours", "--no-edit", "origin/main")
        g("push", "-q", "origin", "main")
        print(f"☁️ السجل اترفع على جيت هوب (دورة {tag})", flush=True)
    except Exception as e:
        print(f"☁️ الرفع اتعذّر ({type(e).__name__}: {str(e)[:60]}) — بنكمل", flush=True)


def _recent_titles(limit: int = 300) -> list[str]:
    """عناوين آخر الفيديوهات المنشورة (من state) — عشان مانكررش عنوان."""
    out: list[str] = []
    for path in ("state/published.json", "state/queue.json"):
        try:
            d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        for v in (d.get("videos") or []):
            t = v.get("title")
            if t:
                out.append(str(t))
            if len(out) >= limit:
                return out
    return out


def shift(hours: float = 5.0, per_hour: int = 1, out_dir=None, every_min: int = 120) -> dict:
    """🔁 وردية طويلة: بتنشر بنفسها كل ساعة من غير ما تحتاج كرون كل ساعة.

    الجدولة **مطلقة** (مش بعدّاد دورات): كل نشرة بتحدد موعد النشرة اللي بعدها من وقت
    النشر الفعلي — عشان لو حد تاني نزل قبلي (بوابة الإيقاع) الوردية ماتأجّلش نفسها ساعات.
    """
    import time as _t
    started = _t.time()
    deadline = started + max(0.2, hours) * 3600.0
    _every = max(15, min(60, int(every_min))) * 60        # ⏱️ ١٥–٦٠ دقيقة (كانت بتطلع ١٥ ساعة!)
    done, cycle = [], 0
    next_at = started
    while _t.time() < deadline:
        now = _t.time()
        if now < next_at:                                # 😴 وقت النشرة لسه مجاش
            _nap = min(next_at - now, max(0.0, deadline - now))
            if _nap <= 1:
                break
            print(f"😴 نوم {_nap/60:.0f} دقيقة لحد النشرة الجاية", flush=True)
            _t.sleep(_nap)
            continue
        cycle += 1
        left_h = (deadline - _t.time()) / 3600.0
        print(f"\n⏱️ وردية — دورة {cycle} (كل {int(_every/60)} دقيقة) · باقي {left_h:.2f} ساعة", flush=True)
        stopped = None
        try:
            out = run("short", max(1, per_hour), out_dir=out_dir, catchup=True)
            for line in out["lines"]:
                print("•", line)
            stopped = out.get("stopped")
            done.append({"cycle": cycle, "slots": out.get("slots"), "stopped": stopped})
        except Exception as e:
            print(f"⚠️ دورة فشلت ({type(e).__name__}: {str(e)[:90]}) — بنكمل الدورة الجاية", flush=True)
            done.append({"cycle": cycle, "error": type(e).__name__})
            stopped = "error"
        now = _t.time()
        if stopped == "quota":            # الحصة خلصت فعليًا من يوتيوب ⇒ ننام ونستأنف
            left_h = (deadline - now) / 3600.0
            if left_h < 0.8:
                print("⛔ الحصة خلصت — باقي وقت قليل فبننهي الوردية", flush=True)
                break
            print(f"⛔ الحصة خلصت — نوم ٤٥ دقيقة وبعدها نجرب تاني (باقي {left_h:.1f} ساعة)", flush=True)
            next_at = now + 45 * 60
            continue
        if stopped == "gate":             # ⏳ حد تاني نزل قريب ⇒ نجرب بعد شوية (بلا تأجيل للنشرة الجاية)
            next_at = now + 12 * 60
            print("⏳ بوابة الإيقاع: نجرب تاني بعد ١٢ دقيقة", flush=True)
            continue
        _sync_state(str(cycle))           # ☁️ نحفظ فورًا بعد كل نشرة ناجحة
        next_at = now + _every            # ⏱️ النشرة الجاية بعد _every من النشر الفعلي
    return {"cycles": cycle, "published": sum(1 for d in done if d.get("slots")), "log": done,
            "hours": round((_t.time() - started) / 3600.0, 2)}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="مصنع Dollars")
    ap.add_argument("--hourly", action="store_true", help="شورت واحد على الخطة")
    ap.add_argument("--daily", action="store_true", help="طويل نوم + قصة")
    ap.add_argument("--kind", choices=["short", "long"], default=None)
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--catchup", action="store_true",
                    help="يعوّض الأدوار اللي فاتت في خطة النهاردة (لو الساعة اتأخرت)")
    ap.add_argument("--force-stage", action="store_true", help="ما تنشرش حتى لو القناة مربوطة")
    ap.add_argument("--out", default=None)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--render-queue", action="store_true", help="يعيد إنتاج الطابور وينشره (لبعد ربط القناة)")
    ap.add_argument("--quota", action="store_true", help="يعرض حصة النشر اليومية لكل مشروع جوجل")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--shift", action="store_true",
                    help="🔁 وردية متواصلة: بتنشر كل ساعة بنفسها (بتحل مشكلة تأخّر/إلغاء الكرون)")
    ap.add_argument("--hours", type=float, default=5.0, help="طول الوردية بالساعات (أقصى 5.5 لأمان جيت هوب)")
    ap.add_argument("--per-hour", type=int, default=1, help="كام فيديو في الدورة")
    ap.add_argument("--every-min", type=int, default=120,
                    help="⏱️ كل كام دقيقة ينشر (دلوقتي ١٢٠ = فيديو كل ساعتين · ٦٠ = كل ساعة)")
    a = ap.parse_args(argv)
    if a.shift:
        out = shift(hours=min(5.5, max(0.3, a.hours)), per_hour=max(1, a.per_hour),
                    out_dir=a.out, every_min=int(os.environ.get("DOLLARS_EVERY_MIN") or a.every_min))
        print("\n" + report_text())
        print(f"\n🔁 الوردية خلصت: {out['cycles']} دورة · نشرت {out['published']} مرة · "
              f"مدة {out['hours']:.2f} ساعة")
        return 0 if out["cycles"] else 1
    if a.status:
        print(report_text())
        return 0
    if a.quota:
        from engine import publish as _pb
        rep = _pb.quota_report()
        print(f"📊 حصة النشر اليومية — {rep['date']}")
        total_left = 0
        for num, info in rep["projects"].items():
            mark = "✅" if info["ready"] else "⚪ (مش مضبوط)"
            print(f"  • مشروع {num}: مستخدم {info['used']}/{info['cap']} · فاضل {info['left']}  {mark}")
            total_left += info["left"] if info["ready"] else 0
        print(f"\n  السقف اليومي المتاح: ~{total_left} رفعة")
        return 0
    if a.render_queue:
        out = render_queue(force_stage=a.force_stage, limit=a.limit, out_dir=a.out)
        for line in out["lines"]:
            print("•", line)
        print(f"\nاتنفّذ: {out['processed']} · فاضل في الطابور: {out['remaining']}")
        return 0            # ✅ التفريغ نجح كخطوة حتى لو مفيش نشر (الحصة مثلًا) — الحفظ لازم يشتغل
    kinds = []
    if a.daily:
        kinds = [("long", max(1, a.count))]
        if _jload(STATE / "queue.json") is not None and not a.kind:
            kinds.append(("story", 1))
    elif a.hourly:
        kinds = [("short", max(1, a.count))]
    elif a.kind:
        kinds = [(a.kind, max(1, a.count))]
    else:
        kinds = [("short", 1)]
    total = 0
    stopped_quota, stopped_gate = False, False
    for kind, cnt in kinds:
        out = run(kind, cnt, force_stage=a.force_stage, out_dir=a.out, catchup=a.catchup)
        total += out["slots"]
        stopped_quota = stopped_quota or (out.get("stopped") == "quota")
        # ⏳ التوقّف بسبب بوابة الإيقاع = توقّف سليم مقصود (مش فشل) ⇒ كود خروج 0
        stopped_gate = stopped_gate or (out.get("stopped") == "gate")
        for line in out["lines"]:
            print("•", line)
    print("\n" + report_text())
    # ⛔ الحصة خلصت = توقف سليم (مش فشل) ⇒ كود خروج 0 عشان خطوات حفظ ال
    #    الذاكرة/الأرشيف تشتغل، والسير ميبانش أحمر من غير سبب.
    return 0 if (total or stopped_quota or stopped_gate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
