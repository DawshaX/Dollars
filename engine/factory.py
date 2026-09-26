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
import pathlib
import re
import random
import sys
import time
import traceback
from datetime import date, datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import agent, editor, meta, publish, visuals  # noqa: E402

QUEUE_CAP = 72                  # أقصى عدد وصفات محفوظة في الطابور
STATE = ROOT / "state"
WORK = ROOT / "work"


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
                        force_stage: bool = False) -> dict:
    """فيديو من **صور حقيقية** (NASA · Wikimedia · Pixabay · Pexels) بحركة سينمائية + نص على الشاشة.

    ده بيستخدم لكل أنواع المحتوى اللي طبيعتها صور حقيقية: الحقائق · الفضاء والطبيعة · وبكground للحكايات.
    """
    import subprocess
    from engine import photo, proc
    gid = idea.get("genre") or "facts"
    topic = idea.get("image_query") or idea.get("topic") or idea.get("kw") or "nature"
    style = "illustration" if gid == "story" else "photo"
    min_color = 0.0 if gid in ("space_nature", "story") else 0.055    # الحقائق: صور ملوّنة حقيقية
    # بحث على مراحل: لو الصور قليلة، بنقصّ الاستعلام أو بنجرب صيغة تانية ⇒ مفيش فيديو بصورة واحدة
    variants, seen = [], set()
    base = str(topic).strip()
    for q in (base, " ".join(base.split()[:3]), " ".join(base.split()[:2]),
              " ".join(base.split()[:1]) + " nature"):
        if q and q.lower() not in seen:
            seen.add(q.lower()); variants.append(q)
    items, paths = [], []
    for q in variants:
        try:
            got = photo.collect(q, genre=gid, n=6, style=style)
        except Exception:
            continue
        for it in got:
            key = (it.get("url") or it.get("page") or "")[:120]
            if key and key not in {((x.get("url") or x.get("page") or "")[:120]) for x in items}:
                items.append(it)
        paths = [p for p in (photo.download(it, min_color=min_color) for it in items) if p]
        if len(paths) >= 4:                # كفاية: ٤ صور = ريل متنوّع
            break
    if not paths:
        raise RuntimeError("مفيش صور حرة متاحة للموضوع ده — نجرب غيره")
    out_dir = pathlib.Path(out_dir or (WORK / f"{date.today().isoformat()}_photo"))
    out_dir.mkdir(parents=True, exist_ok=True)
    from engine import genres as _g
    pal = _g.palette_hex(idea.get("palette"))
    texts = []
    if idea.get("hook"):
        texts.append({"at": 0.4, "dur": 2.6, "text": idea["hook"], "pos": "lower", "size": 0.06})
    style = idea.get("montage") or ""
    lines = idea.get("lines") or []
    step = max(4.0, seconds / (len(lines) + 1)) if lines else 0
    for i, ln in enumerate(lines[:4]):
        texts.append({"at": 3.0 + i * step, "dur": step * 0.9, "text": ln, "pos": "lower", "size": 0.048})
    if gid in ("facts", "space_nature"):
        texts.append({"at": max(1.0, seconds - 3.0), "dur": 3.0,
                      "text": "Source: " + (idea.get("source") or "NASA / Wikimedia"), "pos": "lower", "size": 0.032})
    if gid == "story":                    # الحكاية بلا كلام: من غير سطور حقيقة
        texts = [tx for tx in texts if tx.get("text") == idea.get("hook")]
    silent = out_dir / f"photo_{seed}.mp4"
    photo.render_reel(paths, silent, seconds=seconds, w=720, h=1280, fps=30, palette=pal,
                      seed=seed, texts=texts)
    # الصوت: صوت من صنعنا + موسيقى (نفس منظومة المصنع)
    from engine import editor as _ed
    audio = _ed.mix_audio(seconds, [], ambient_name=idea.get("audio"),
                          music_style=idea.get("music") or "dream_pulse", music_gain=0.5)
    wav = out_dir / f"photo_{seed}.wav"
    _ed._write_wav(wav, audio)
    video = out_dir / f"{gid}_{seed}.mp4"
    subprocess.run([proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(video)], check=True)
    silent.unlink(missing_ok=True); wav.unlink(missing_ok=True)
    from engine import meta
    md = meta.build({**(idea.get("md_spec") or {}), **(idea.get("spec_extra") or {}), "genre": gid,
                     "pillar": g["pillar"] if (g := _g.get(gid)) else idea.get("pillar"),
                     "kind": "short", "seconds": int(seconds), "kw": idea.get("kw"),
                     "lines": lines, "source": idea.get("source"),
                     "title_style": idea.get("title_style"), "scene": idea.get("scene")})
    cr = photo.credits(items)
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
    md["sources"] = [it.get("page") for it in items if it.get("page")]
    md["shot_list"] = [{"scene": f"photo:{it.get('source')}", "dur": round(seconds / max(1, len(paths)), 2),
                        "move": "kenburns", "sfx": [], "fx": []} for it in items[:len(paths)]]
    # 🖼️ الغلاف: من أقوى صورة + نص قصير (زي أغلفة القنوات الكبيرة)
    thumb = None
    try:
        ttexts = {
            "facts": ["3 FACTS", (idea.get("kw") or "")[:22]],
            "space_nature": [(idea.get("kw") or "").upper()[:20], f"{int(seconds)}s BLACK SCREEN"],
            "story": ["A WORDLESS STORY", (idea.get("thing") or "")[:22]],
        }.get(gid, [(idea.get("kw") or idea.get("topic") or "")[:22].upper(), f"{int(seconds)}s"])
        thumb = photo.thumb_from_photo(paths, ttexts, out_dir / f"{gid}_{seed}_thumb.jpg", palette=pal)
    except Exception:
        thumb = None
    return {"kind": "photo_short", "video": str(video), "meta": md, "pillar": md.get("pillar"),
            "thumbnail": str(thumb) if thumb else None,
            "duration": f"{int(seconds)}s", "scene": f"photo:{topic}", "audio": idea.get("audio"),
            "palette": idea.get("palette"), "genre": gid, "photos": len(paths),
            "credits": cr}


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
    return plan


def next_slots(kind: str = "short", count: int = 1, date_str: str | None = None) -> list:
    """أدوار لسه ما اتعملتش من خطة اليوم (شورت / طويل)."""
    plan = _plan(date_str)
    led = _load_ledger()
    done = {(d.get("date"), d.get("hour"), d.get("kind")) for d in led.get("done", [])}
    out = []
    for s in plan.get("slots", []):
        if s.get("kind") != kind:
            continue
        if (plan["date"], s["hour"], kind) in done:
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
        rec = ed.make("sleep_long", hours=hours, scene=scene, audio=audio, **style_kw)
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

    # 🚦 بوابة الجودة: الفيديو البايظ **مايتنشرش** (بس بنحفظه في الطابور عشان يتراجع)
    quality_block = None
    try:
        from engine import quality
        passed, qrep = quality.gate(video, kind=("long" if rec.get("kind") == "long" else "short"),
                                    seconds=None, strict=True)
        rec["quality"] = {"pass": passed, "failed": qrep.get("failed") or qrep.get("error")}
        if not passed:
            quality_block = f"🚦 بوابة الجودة رفضت النشر: {qrep.get('failed') or qrep.get('error')}"
            _say(f"   {quality_block}")
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
    items = q["items"][:limit] if limit else list(q["items"])
    lines, done = [], 0
    try:                                     # نسأل قبل ما نصرف ٥ دقايق رندر على الفاضي
        left = publish.remaining_capacity()
        if publish.usable_projects() and left <= 0:
            _say("⛔ الحصة اليومية خلصت على كل المشاريع — مش بنرندر عشان ما نضيّعش وقت. "
                 "الطابور زي ما هو وهينزل لوحده أول ما الحصة ترجع.")
            return {"processed": 0, "remaining": len(items), "lines": ["⛔ الحصة خلصت"], "stopped": "quota"}
        _say(f"♻️ تفريغ الطابور: {len(items)} عنصر · سعة النشر المتبقية النهاردة: {left} رفعة")
    except Exception:
        pass
    _say(f"♻️ تفريغ الطابور: {len(items)} عنصر · رندر + نشر عنصر عنصر")
    for n, it in enumerate(items, 1):
        slot = it.get("slot")
        if not slot:
            continue
        try:
            if publish.usable_projects() and publish.remaining_capacity() <= 0:
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
            if res.get("published") and not force_stage:
                q["items"].remove(it)
            elif quota_exhausted(res):
                lines.append("⛔ كوتة يوتيوب خلصت — وقفنا بدل ما نضيّع وقت. الباقي هينزل لوحده (كل ساعة).")
                _jdump(STATE / "queue.json", q)
                _log(lines)
                return {"processed": done, "remaining": len(q["items"]), "lines": lines, "stopped": "quota"}
        except Exception as e:
            _say(f"[{n}/{len(items)}] ❌ خطأ: {type(e).__name__}: {str(e)[:300]}")
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
        catchup: bool = False, max_catchup: int = 4) -> dict:
    if catchup:
        miss = missed_slots(kind)
        # الشورتس: نعوّض لحد 4 في التشغيل الواحد · الطويلة: واحدة بالكتير (ثقيلة أوي)
        count = max(count, min(max_catchup, miss)) if kind == "short" else max(count, min(2, miss))
    slots = next_slots(kind, count)
    lines, results = [], []
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
    a = ap.parse_args(argv)
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
        return 0 if out["processed"] else 1
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
    for kind, cnt in kinds:
        out = run(kind, cnt, force_stage=a.force_stage, out_dir=a.out, catchup=a.catchup)
        total += out["slots"]
        for line in out["lines"]:
            print("•", line)
    print("\n" + report_text())
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
