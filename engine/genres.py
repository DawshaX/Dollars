"""
🎭 محرّك الأنواع — ٨ أنواع متنوّعة، كل نوع وله هويته الكاملة.
==============================================================
القاعدة الحديدية (سياسة يوتيوب «المحتوى غير الأصيل»):
    **ممنوع فيديوهين متشابهين.** كل نوع له: مشاهد · صوت · إيقاع مونتاج · شكل عنوان · وقت نشر · بلايليست.
وده اللي يخلي النشر الكثيف آمن: التنوّع حقيقي، مش قالب واحد بيتكرر.

    from engine import genres
    g = genres.get("satisfying")
    genres.pick_recipe(gid, recent=variety.recent(), seed=123)   # تركيبة جديدة مضمونة
"""
from __future__ import annotations

import random

# ── الأنواع (المفتاح = المعرّف) ──────────────────────────────────────────────
GENRES: dict[str, dict] = {
    "sleep_ambience": {
        "ar": "نوم وأمبيانس", "pillar": "sleep", "kinds": ("long", "short"),
        "durations": {"long": ["3h", "8h", "10h", "12h"], "short": ["30s", "45s", "60s", "90s"]},
        "scenes": ["rain_glass", "ocean_night", "fireplace", "storm_window", "snow_night",
                   "train_window", "forest_night", "beach_night", "valley_lake", "starfield"],
        "audio": ["sleep_rain", "ocean", "fireplace", "storm", "snow", "train", "night_forest",
                  "beach", "calm_night"],
        "mood": ["calm", "cozy", "deep"],
        "palettes": ["midnight", "deep_blue", "warm_ember", "cool_slate"],
        "montage": ["طويل هادي", "مشهد واحد مستمر", "تنفّس بطيء"],
        "title_styles": ["{kw} for Sleeping | {dur} Black Screen | Deep Sleep",
                         "{kw} • {dur} • Fall Asleep Fast (No Music)",
                         "Sleep in Minutes: {kw} for {dur}",
                         "{kw} — {dur} of Pure Calm | Insomnia Relief"],
        "desc_intro": "{kw} — {dur} of continuous, loop-friendly ambience to help you sleep, "
                      "study or calm down. Black screen, no talking, nothing taken from anyone.",
        "tags": ["sleep sounds", "rain sounds for sleeping", "black screen", "insomnia relief",
                 "deep sleep", "white noise", "ambience", "relaxing sounds", "8 hours", "10 hours"],
        "playlist": "Sleep & Nature",
        "dayparts": {"night": 5, "evening": 4, "morning": 1, "midday": 1},
        "hooks_en": ["Sleep in 3 minutes", "For tonight", "Turn the lights off",
                     "Let your brain switch off"],
        "thumb_styles": ["مشهد طبيعي + رقم المدة", "شاشة سوداء + نص واضح", "نافذة مطر + ساعة"],
        "text_policy": "none",
    },
    "focus_study": {
        "ar": "تركيز ودراسة", "pillar": "focus", "kinds": ("long", "short"),
        "durations": {"long": ["2h", "3h", "4h"], "short": ["30s", "45s", "60s"]},
        "scenes": ["library_rain", "cafe_soft", "desk_window", "rain_glass", "snow_window",
                   "brown_noise", "forest_night"],
        "audio": ["focus", "brown", "rain_soft", "cafe", "library"],
        "mood": ["focused", "clean", "steady"],
        "palettes": ["cool_slate", "paper_warm", "deep_blue"],
        "montage": ["خط زمني وفصول", "مشهد ثابت + ساعة", "بومودورو"],
        "title_styles": ["{kw} for Studying & Focus | {dur} | Deep Work, No Music",
                         "Study With Me — {kw} ({dur}) | Pomodoro Chapters",
                         "{kw} • {dur} • Concentration & Calm"],
        "desc_intro": "{kw} for {dur} — built for deep work, revision and coding sessions. "
                      "Steady noise, no lyrics, no interruptions.",
        "tags": ["study with me", "focus music", "deep work", "brown noise", "concentration",
                 "pomodoro", "library ambience", "no music"],
        "playlist": "Focus & Study",
        "dayparts": {"morning": 5, "midday": 4, "evening": 2, "night": 1},
        "hooks_en": ["3-hour deep work block", "Set a timer", "One task only",
                     "Phone in another room"],
        "thumb_styles": ["مكتب + مؤقت", "كتاب مفتوح + رقم الساعات", "نافذة مطر + لابتوب"],
        "text_policy": "none",
    },
    "story": {
        "ar": "حكايات", "pillar": "story", "kinds": ("short", "long"),
        "durations": {"short": ["45s", "60s", "90s"], "long": ["10m", "15m", "20m"]},
        "scenes": ["story_valley", "story_cloud", "story_forest", "story_harbor", "story_desert",
                   "story_city_rain", "story_mountain"],
        "audio": ["story_gentle", "story_hopeful", "story_mystery"],
        "mood": ["warm", "curious", "tender"],
        "palettes": ["story_warm", "story_dusk", "story_dream"],
        "montage": ["مشهد ← مشهد بإيقاع", "لحظة توقف ← حركة", "نهاية لطيفة"],
        "title_styles": ["{name} and {thing} — a wordless story",
                         "The {thing} | a tiny wordless tale",
                         "{name}'s Little {thing} — a story without words"],
        "desc_intro": "A short wordless story you can follow in any language. "
                      "Made frame by frame in our studio.",
        "tags": ["wordless story", "animated short", "story without words", "wholesome",
                 "bedtime story", "short film", "animation"],
        "playlist": "Wordless Stories",
        "dayparts": {"evening": 4, "night": 3, "morning": 2, "midday": 2},
        "hooks_en": ["Wait for the ending", "It only takes a minute", "A little story"],
        "thumb_styles": ["البطل + تعبير", "لحظة الذروة", "خلفية حالمة + العنوان"],
        "text_policy": "none",
    },
    "satisfying": {
        "ar": "مُرضي و ASMR", "pillar": "satisfying", "kinds": ("short",),
        "durations": {"short": ["15s", "20s", "30s", "45s", "60s"]},
        "scenes": ["sand_table", "kinetic_sand", "bubbles", "ice_crush", "domino", "magnet_beads",
                   "soap_cut", "water_rings", "hydraulic", "glass_sand"],
        "audio": ["asmr_soft", "asmr_crisp", "water_soft"],
        "mood": ["satisfying", "crisp", "smooth"],
        "palettes": ["clean_bright", "pastel_soft", "high_contrast"],
        "montage": ["قطع سريع على الإيقاع", "لقطة واحدة متصلة", "٤ مقاطع متساوية"],
        "title_styles": ["{kw} — oddly satisfying ({dur})",
                         "Wait for it… {kw} #oddlysatisfying",
                         "{kw} that hits different ({dur})",
                         "Perfect {kw} — no talking, just calm"],
        "desc_intro": "{kw} — rendered frame by frame in our studio. "
                      "Sound and visuals made by us, nothing taken from anyone.",
        "tags": ["oddly satisfying", "satisfying video", "asmr", "kinetic sand", "bubbles",
                 "no talking", "relaxing video", "satisfying compilation"],
        "playlist": "Satisfying & ASMR",
        "dayparts": {"evening": 4, "midday": 3, "morning": 2, "night": 3},
        "hooks_en": ["Wait for it", "Watch it settle", "Perfectly smooth"],
        "thumb_styles": ["لقطة قريبة جدًا", "نصف قبل / نصف بعد", "لون صارخ + حركة"],
        "text_policy": "none",
    },
    "facts": {
        "ar": "علم وحقائق موثّقة", "pillar": "satisfying", "kinds": ("short",),
        "durations": {"short": ["30s", "45s", "60s"]},
        "scenes": ["starfield", "planet_surface", "earth_from_space", "micro_world",
                   "ocean_deep", "volcano", "ice_flow", "desert_dunes"],
        "audio": ["curious", "space_calm", "discovery"],
        "mood": ["curious", "bright"],
        "palettes": ["deep_blue", "cosmic", "earth_tone"],
        "montage": ["٣ حقائق ← ٣ مشاهد", "عدّاد تصاعدي", "سؤال ← جواب"],
        "title_styles": ["3 Facts About {kw} You Didn't Know",
                         "What {kw} Actually Looks Like — 3 Real Facts",
                         "{kw}: 3 Verified Facts (Sources Included)"],
        "desc_intro": "3 facts about {kw}, each one with its source linked below — "
                      "nothing invented, everything checkable.",
        "tags": ["facts", "science facts", "did you know", "space facts", "documentary",
                 "verified facts", "science shorts"],
        "playlist": "Facts & Science",
        "dayparts": {"evening": 4, "midday": 4, "morning": 3, "night": 2},
        "hooks_en": ["You've had this wrong", "3 facts — sources below", "Look closer"],
        "thumb_styles": ["صورة حقيقية + رقم ٣", "مقارنة حجم", "سهم على تفصيلة"],
        "text_policy": "en_lines",     # نص إنجليزي على الشاشة (مصدر حقيقي موثّق)
    },
    "space_nature": {
        "ar": "فضاء وطبيعة", "pillar": "sleep", "kinds": ("short", "long"),
        "durations": {"short": ["30s", "45s", "60s"], "long": ["3h"]},
        "scenes": ["starfield", "nebula_flow", "earth_from_space", "aurora", "ocean_deep",
                   "glacier", "volcano", "canyon"],
        "audio": ["space_calm", "cosmic", "ocean", "wind_deep"],
        "mood": ["awe", "calm"],
        "palettes": ["cosmic", "deep_blue", "aurora"],
        "montage": ["كشف بطيء", "تحوّل تدريجي", "رحلة مستمرة"],
        "title_styles": ["{kw} — a slow look at the universe ({dur})",
                         "The Real {kw} in Motion | {dur}",
                         "{kw}: Beautiful and Relaxing ({dur} Black Screen)"],
        "desc_intro": "{kw} — a calm, cinematic look at real places and real skies "
                      "(imagery from public NASA / Wikimedia sources, animated by us).",
        "tags": ["space", "nasa", "nature", "relaxation", "earth from space", "aurora",
                 "documentary visuals", "4k relaxation"],
        "playlist": "Space & Earth",
        "dayparts": {"night": 4, "evening": 4, "midday": 2, "morning": 2},
        "hooks_en": ["Real footage inspired", "Look how slow this is", "From above"],
        "thumb_styles": ["صورة ناسا + نص قصير", "كوكب + رقم الساعات", "طبقات ضوء"],
        "text_policy": "en_lines_label",   # سطر صغير باسم المصدر (شفافية)
    },
    "fun_memes": {
        "ar": "طرائف وميمز", "pillar": "satisfying", "kinds": ("short",),
        "durations": {"short": ["15s", "20s", "30s"]},
        "scenes": ["meme_kitchen", "meme_office", "meme_gym", "meme_traffic", "meme_park",
                   "sand_table", "bubbles"],
        "audio": ["fun_beat", "pop_bright"],
        "mood": ["funny", "light"],
        "palettes": ["vivid_pop", "high_contrast", "pastel_soft"],
        "montage": ["مقطع ٣ ثواني ← ضربة", "بناء ← نتيجة", "مفارقة"],
        "title_styles": ["When {kw}… #funny",
                         "POV: {kw} #memes",
                         "{kw} — we've all been there"],
        "desc_intro": "A small silent comedy from our studio — our own characters, no clips taken "
                      "from anyone.",
        "tags": ["funny", "memes", "silent comedy", "animation meme", "short comedy",
                 "no talking funny"],
        "playlist": "Fun & Memes",
        "dayparts": {"evening": 4, "midday": 3, "night": 2, "morning": 2},
        "hooks_en": ["POV", "Every single time", "Wait for the ending"],
        "thumb_styles": ["وش الشخصية في ذروة الموقف", "قبل/بعد مضحك", "سهم + تعبير"],
        "text_policy": "none",
    },
    "calm_wellness": {
        "ar": "تهدئة وتنفّس", "pillar": "focus", "kinds": ("short", "long"),
        "durations": {"short": ["45s", "60s"], "long": ["5m", "10m", "15m"]},
        "scenes": ["breath_circle", "ocean_calm", "forest_night", "aurora", "water_rings"],
        "audio": ["breath_soft", "calm_night", "ocean"],
        "mood": ["calm", "kind"],
        "palettes": ["pastel_soft", "aurora", "deep_blue"],
        "montage": ["دائرة تنفّس", "موجات هادئة", "إيقاع ٤-٧-٨"],
        "title_styles": ["Breathe with me — {dur} of calm",
                         "Calm Down in {dur} | Guided Breathing (No Talk)",
                         "{dur} to Slow Down | Soft Visual Breathing"],
        "desc_intro": "{dur} of slow, wordless breathing visuals — follow the circle. "
                      "General wellbeing only, not medical advice.",
        "tags": ["breathing exercise", "calm", "relaxation", "anxiety relief", "mindfulness",
                 "sleep better", "short meditation"],
        "playlist": "Calm & Breathe",
        "dayparts": {"evening": 4, "night": 3, "morning": 3, "midday": 2},
        "hooks_en": ["Breathe in… hold… out", "Follow the circle", "Slower than yesterday"],
        "thumb_styles": ["دائرة تنفّس + نص", "غروب + موج", "لون باستيل + كلمة واحدة"],
        "text_policy": "none",
    },
}

SHORTS = [g for g, v in GENRES.items() if "short" in v["kinds"]]
LONGS = [g for g, v in GENRES.items() if "long" in v["kinds"]]


def get(gid: str) -> dict:
    return GENRES.get(gid) or GENRES["satisfying"]


def daypart(hour_utc: int) -> str:
    """فترات اليوم (بتوقيت UTC): الفجر/الصبح · الظهر · المسا · الليل."""
    if 2 <= hour_utc < 8:
        return "morning"
    if 8 <= hour_utc < 15:
        return "midday"
    if 15 <= hour_utc < 21:
        return "evening"
    return "night"


def weighted_pick(hour_utc: int, rng: random.Random, allow: list[str] | None = None) -> str:
    """يختار نوع مناسب للوقت — عشان الجمهور المستهدف يكون صاحي."""
    part = daypart(hour_utc)
    ids = allow or SHORTS
    weights = [get(g)["dayparts"].get(part, 1) for g in ids]
    return rng.choices(ids, weights=weights, k=1)[0]


def title_for(gid: str, rng: random.Random, **fmt) -> str:
    style = rng.choice(get(gid)["title_styles"])
    try:
        return style.format(**fmt)[:100]
    except Exception:
        return style


def tags_for(gid: str, extra: list[str] | None = None, limit_chars: int = 480) -> list[str]:
    out, total = [], 0
    for t in (get(gid)["tags"] + (extra or [])):
        if total + len(t) + 1 > limit_chars:
            break
        if t not in out:
            out.append(t); total += len(t) + 1
    return out
