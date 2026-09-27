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
# لوحات كل نوع (٣ ألوان هيكس) — bالوحة بتحدد هوية الألوان في الرندر
PALETTE_HEX = {
    "midnight": ["#05070f", "#101c33", "#39507a"],
    "deep_blue": ["#06101f", "#12294a", "#5b86b8"],
    "warm_ember": ["#140a06", "#5d2a12", "#ff9d4d"],
    "cool_slate": ["#0c1218", "#26333d", "#8aa3b0"],
    "paper_warm": ["#1a140d", "#5c4a33", "#e8d9bd"],
    "cosmic": ["#080b1a", "#2a1f4d", "#c9a2ff"],
    "earth_tone": ["#0f0d08", "#4a3b22", "#d8b071"],
    "aurora": ["#04121a", "#0f4a52", "#7ef0c0"],
    "story_warm": ["#1a0f0a", "#6b3a1f", "#ffcf8a"],
    "story_dusk": ["#140d1a", "#3f2a53", "#e5a0c0"],
    "story_dream": ["#0a0f1a", "#2a3a63", "#a9c7ff"],
    "clean_bright": ["#1a1a1a", "#6e6e6e", "#f2f2f2"],
    "pastel_soft": ["#2a2430", "#7a6a86", "#ffd9ea"],
    "high_contrast": ["#000000", "#4a4a4a", "#ffffff"],
    "vivid_pop": ["#1a0a1a", "#7a2a6a", "#ffe14d"],
}


def palette_hex(name: str | list | None) -> list:
    """يحوّل اسم اللوحة لألوان هيكس (أو يرجّعها زي ما هي)."""
    if isinstance(name, (list, tuple)):
        return list(name)
    return PALETTE_HEX.get(str(name), PALETTE_HEX["deep_blue"])


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

# ═══════════════════════════════════════════════════════════════════════════
# 🆕 أنواع ٢٠٢٦ المضافة: ASMR · راحة نفسية · ضحك · مطر وطبيعة
#    (كلها أنواع **الناس بتدور عليها** فعلًا وبتحقق مشاهدات عالية)
# ═══════════════════════════════════════════════════════════════════════════
GENRES["asmr"] = {
    "ar": "إيه‑إس‑إم‑آر", "pillar": "satisfying", "kinds": ["short", "long"],
    "durations": {"short": ["30s", "45s", "60s"], "long": ["30m", "1h", "2h"]},
    "scenes": ["sand_table", "bubble_lamp", "candle_desk", "zen_garden", "harmonograph"],
    "audio": ["room_tone", "rain", "fire"],
    "mood": ["قريب", "ناعم", "مريح"],
    "palettes": ["warm_amber", "pastel_soft", "night_blue"],
    "montage": ["تفاصيل قريبة جدًا", "لمس وإيقاع هادي", "إضاءة دافئة"],
    "title_styles": ["ASMR {topic} (No Talking)", "ASMR {topic} — {dur} of pure sounds",
                     "Tingly ASMR: {topic}"],
    "desc_intro": "{dur} of close-up ASMR sounds and textures — no talking, just the sound. "
                  "Headphones recommended.",
    "tags": ["asmr", "asmr no talking", "tingles", "sleep aid", "relaxing sounds",
             "close up", "satisfying sounds"],
    "playlist": "ASMR Sounds", "dayparts": {"night": 4, "evening": 3, "midday": 2, "morning": 2},
    "hooks_en": ["Turn your volume up", "Headphones on", "Close your eyes…"],
    "thumb_styles": ["تفصيلة قريبة + كلمة ASMR", "خلفية دافئة + نص ناعم", "إيموجي ✨ + كلمتين"],
    "text_policy": "hook_only",
}

GENRES["comfort_relax"] = {
    "ar": "راحة نفسية وتهدئة", "pillar": "sleep", "kinds": ["short", "long"],
    "durations": {"short": ["30s", "45s"], "long": ["1h", "2h", "3h"]},
    "scenes": ["candle_desk", "rain_glass", "fireplace", "ocean", "forest_night"],
    "audio": ["rain", "fire", "waves", "room_tone"],
    "mood": ["دافي", "مطمئن", "ناعم"],
    "palettes": ["warm_amber", "pastel_soft", "sunset_warm"],
    "montage": ["مشاهد دافية", "إيقاع بطيء", "إحساس بيت"],
    "title_styles": ["{dur} of pure comfort", "Comforting {topic} — let it slow down",
                     "Cozy {topic} (No Music Needed)"],
    "desc_intro": "{dur} of cozy, calming {topic}. Made for anxious nights, long days and "
                  "the moments you just need to breathe. General wellbeing only.",
    "tags": ["comfort", "relaxation", "calm", "anxiety relief", "cozy", "peaceful",
             "stress relief"],
    "playlist": "Comfort & Calm", "dayparts": {"night": 5, "evening": 4, "midday": 2, "morning": 2},
    "hooks_en": ["You're safe here", "It's okay to slow down", "Breathe with this one"],
    "thumb_styles": ["شمعة + كلمة دافية", "مطر على الشباك", "مشهد بيت + نص ناعم"],
    "text_policy": "hook_only",
}

GENRES["funny"] = {
    "ar": "ضحك وكوميدي", "pillar": "satisfying", "kinds": ["short"],
    "durations": {"short": ["15s", "20s", "30s"]},
    "scenes": ["stinger_zoom", "stinger_confetti", "stinger_glitch", "neon_rain", "bubble_lamp"],
    "audio": ["room_tone", "rain"],
    "mood": ["مبسوط", "سريع", "خفيف"],
    "palettes": ["vivid_bright", "sunset_warm", "neon_pop"],
    "montage": ["قطع سريع", "زوم مضحك", "مؤثرات صوتية"],
    "title_styles": ["POV: {topic} 😭", "Nobody: … Me: {topic}", "{topic} — why is this so real"],
    "desc_intro": "Relatable comedy about {topic}. If you smiled, subscribe for one more 😅",
    "tags": ["funny", "relatable", "comedy", "shorts", "lol", "meme", "pov"],
    "playlist": "Funny Moments", "dayparts": {"evening": 5, "midday": 4, "night": 3, "morning": 2},
    "hooks_en": ["Wait for it…", "Why is this so accurate 😭", "Tell me I'm not alone"],
    "thumb_styles": ["وش متعجب + نص كبير", "إيموجي 😂 + كلمة", "خلفية ملوّنة + جملة"],
    "text_policy": "en_lines",
}

GENRES["rain_nature"] = {
    "ar": "مطر وطبيعة", "pillar": "sleep", "kinds": ["short", "long"],
    "durations": {"short": ["30s", "45s", "60s"], "long": ["3h", "8h", "10h"]},
    "scenes": ["rain_glass", "neon_rain", "forest_night", "ocean", "aurora"],
    "audio": ["rain", "thunder", "wind", "waves"],
    "mood": ["هادي", "طبيعي", "مريح"],
    "palettes": ["night_blue", "deep_green", "storm_grey"],
    "montage": ["مطر حقيقي", "برق بعيد", "غابات وضباب"],
    "title_styles": ["{topic} for {dur} | Sleep & Study", "Rainy {topic} — {dur} No Music",
                     "{dur} of {topic} (Real Sounds)"],
    "desc_intro": "{dur} of real rain and nature sounds in {topic} — no music, no talking. "
                  "Perfect for sleep, study and deep focus.",
    "tags": ["rain sounds", "nature sounds", "sleep sounds", "study sounds", "rain for sleeping",
             "thunderstorm", "no music"],
    "playlist": "Rain & Nature", "dayparts": {"night": 6, "evening": 4, "midday": 3, "morning": 2},
    "hooks_en": ["Real rain, no music", "Let it rain", "Sleep in 10 minutes"],
    "thumb_styles": ["مطر + كلمة واحدة", "غابة وضباب + نص", "برق بعيد + مدة"],
    "text_policy": "hook_only",
}



# ═══════════════════════════════════════════════════════════════════════════
# 🌍 توسيع ٢٠٢٦: أنواع عالمية متنوعة (الناس بتدور عليها في أي وقت — مش نوم بس)
# ═══════════════════════════════════════════════════════════════════════════
_NEW = {
    "pets_funny": dict(
        ar="حيوانات وبيتس", pillar="satisfying", kinds=("short",),
        durations={"short": ["15s", "20s", "30s"]},
        scenes=["stinger_zoom", "bubble_lamp", "neon_rain"],
        audio=["room_tone", "rain"], mood=["لطيف", "مضحك", "دافي"],
        palettes=["vivid_bright", "sunset_warm", "pastel_soft"],
        montage=["لقطات قريبة للحيوان", "إيقاع خفيف", "لحظة طريفة"],
        title_styles=["This {kw} made my day 🐾", "{kw} being absolutely perfect",
                      "Wait for the {kw}… 🐶", "POV: your {kw} at 3am 😂"],
        desc_intro="{kw} — cute animals doing what they do best. Daily pick-me-up.",
        tags=["pets", "cute animals", "dogs", "cats", "funny animals", "puppy", "kitten",
              "animal shorts", "wholesome"],
        playlist="Cute & Wild", dayparts={"evening": 5, "midday": 4, "morning": 4, "night": 3},
        hooks_en=["Wait for it 🐾", "Volume up for happiness", "You needed this today"],
        thumb_styles=["حيوان لطيف + نص قصير", "لقطة قريبة + إيموجي", "خلفية ملوّنة + كلمتين"],
        text_policy="en_lines"),
    "food_asmr": dict(
        ar="أكل قريب (سمعي)", pillar="satisfying", kinds=("short",),
        durations={"short": ["20s", "30s", "45s"]},
        scenes=["sand_table", "bubble_lamp", "candle_desk"],
        audio=["room_tone", "fire"], mood=["شهي", "قريب", "ناعم"],
        palettes=["warm_amber", "sunset_warm", "vivid_bright"],
        montage=["تقريب شديد", "إيقاع قطع", "تفاصيل الملمس"],
        title_styles=["{kw} — the sound is everything 🤤", "ASMR: {kw} (no talking)",
                      "Wait for the crunch… {kw}", "{kw} at 4K slow motion"],
        desc_intro="{kw} in close-up — crunchy, juicy, satisfying. Headphones recommended.",
        tags=["food asmr", "asmr eating", "satisfying food", "crunchy", "food closeup", "cooking",
              "no talking", "mukbang asmr"],
        playlist="Food & Crunch", dayparts={"evening": 5, "midday": 5, "night": 3, "morning": 2},
        hooks_en=["Headphones on 🎧", "The crunch though…", "0:03 is the best part"],
        thumb_styles=["أكل مقرّب + كلمة", "قطعة لامعة + نص", "لقطة قطع + إيموجي"],
        text_policy="en_lines"),
    "water_nature": dict(
        ar="مياه وطبيعة", pillar="satisfying", kinds=("short", "long"),
        durations={"short": ["30s", "45s", "60s"], "long": ["1h", "2h"]},
        scenes=["ocean", "valley_lake", "forest_night"],
        audio=["ocean", "waves", "rain_soft"], mood=["هادي", "منعش", "طبيعي"],
        palettes=["deep_blue", "cool_slate", "sunset_warm"],
        montage=["حركة كاميرا بطيئة", "تفاصيل الماء", "إيقاع طبيعي"],
        title_styles=["{kw} in 4K — pure calm", "Water you can almost hear: {kw}",
                      "{kw} for {dur} of quiet", "The most calming {kw} on the internet"],
        desc_intro="{kw} — real footage, real sound. Play it in the background whenever you need calm.",
        tags=["water", "nature", "4k nature", "ocean", "waterfall", "relaxing nature", "asmr water",
              "nature sounds"],
        playlist="Water & Nature", dayparts={"morning": 5, "midday": 4, "evening": 3, "night": 3},
        hooks_en=["Sound on 🔊", "Nature at its calmest", "Watch the water settle"],
        thumb_styles=["ماء صافي + إشعاع", "شلال + نص", "بحر + كلمة هادية"],
        text_policy="en_lines"),
    "city_vibes": dict(
        ar="مدن وأجواء", pillar="satisfying", kinds=("short",),
        durations={"short": ["20s", "30s", "45s"]},
        scenes=["neon_rain", "train_window", "stinger_glitch"],
        audio=["room_tone", "cafe", "rain"], mood=["ليل", "نيون", "حيوي"],
        palettes=["neon_pop", "midnight", "cool_slate"],
        montage=["لقطات بمدينة", "حركة سريعة", "تبديل مشاهد"],
        title_styles=["{kw} — 1 minute of city therapy", "Late night {kw} vibes 🌃",
                      "If you love {kw}, this hits", "{kw} · asmr city ambience"],
        desc_intro="{kw} — city mood, real streets, real sounds. Perfect for a focus break.",
        tags=["city", "city ambience", "asmr city", "night city", "street", "urban", "travel",
              "walking tour"],
        playlist="City & Neon", dayparts={"night": 5, "evening": 5, "midday": 2, "morning": 2},
        hooks_en=["Sound on for this one", "City therapy", "Which city is this?"],
        thumb_styles=["نيون ليلي + نص", "شارع مطر + كلمة", "أفق مدينة + إيموجي"],
        text_policy="en_lines"),
    "space_cosmos": dict(
        ar="فضاء وكون", pillar="facts", kinds=("short",),
        durations={"short": ["30s", "45s", "60s"]},
        scenes=["starfield", "ocean_night"],
        audio=["calm_night", "room_tone"], mood=["مهيب", "ساكن", "عميق"],
        palettes=["midnight", "deep_blue", "cool_slate"],
        montage=["زوم فضائي", "لقطات حقيقية", "إيقاع بطيء"],
        title_styles=["3 real space facts that break your brain 🌌", "{kw} — real footage, no CGI",
                      "Earth from above: {kw}", "{kw} will humble you"],
        desc_intro="{kw} — real space footage and verified facts. Sources are official space agencies.",
        tags=["space", "nasa", "universe", "earth from space", "astronomy", "science facts",
              "planets", "cosmos"],
        playlist="Space & Facts", dayparts={"night": 5, "evening": 4, "midday": 3, "morning": 2},
        hooks_en=["Wait for the last one 🌌", "This is real footage", "Look closer"],
        thumb_styles=["كوكب + نص كبير", "نجوم + كلمة", "كرة أرضية + إيموجي"],
        text_policy="facts"),
    "slow_macro": dict(
        ar="ماكرو بطيء", pillar="satisfying", kinds=("short",),
        durations={"short": ["20s", "30s", "45s"]},
        scenes=["candle_desk", "bubble_lamp", "zen_garden"],
        audio=["room_tone", "fire", "rain"], mood=["تفصيلي", "ناعم", "ساحر"],
        palettes=["warm_amber", "pastel_soft", "deep_blue"],
        montage=["تقريب ماكرو", "حركة شديدة البطء", "تفاصيل ملمس"],
        title_styles=["{kw} — 4K macro slow motion", "Nobody watches {kw} just once",
                      "{kw} up close is unreal", "The details in {kw} 🤯"],
        desc_intro="{kw} in extreme close-up slow motion — oddly satisfying textures.",
        tags=["macro", "slow motion", "4k", "satisfying", "closeup", "texture", "oddly satisfying",
              "cinematic"],
        playlist="Macro & Slow", dayparts={"evening": 5, "midday": 4, "night": 4, "morning": 3},
        hooks_en=["Watch till the end", "The detail is unreal", "Slow it down with me"],
        thumb_styles=["لقطة ماكرو + كلمة", "تفصيلة ناعمة + نص", "خلفية داكنة + إيموجي"],
        text_policy="en_lines"),
    "sky_timelapse": dict(
        ar="سماء وتايم لابس", pillar="satisfying", kinds=("short",),
        durations={"short": ["20s", "30s", "45s"]},
        scenes=["starfield", "valley_lake", "beach_night"],
        audio=["calm_night", "rain_soft"], mood=["واسع", "هادي", "ملوّن"],
        palettes=["sunset_warm", "deep_blue", "cool_slate"],
        montage=["تايم لابس", "تحريك سريع", "انتقال ناعم"],
        title_styles=["{kw} in 30 seconds — timelapse", "The sky over {kw} never gets old",
                      "Watch {kw} move", "{kw} timelapse · 4K"],
        desc_intro="{kw} — timelapse of real skies. Watch the clouds do the rest.",
        tags=["timelapse", "sky", "clouds", "sunset", "4k", "nature", "relaxing", "satisfying"],
        playlist="Sky & Light", dayparts={"evening": 5, "morning": 4, "midday": 3, "night": 4},
        hooks_en=["Watch the sky move", "30 seconds of sky", "Wait for the colours"],
        thumb_styles=["سحاب + غروب", "سماء وردية + نص", "نجوم + كلمة"],
        text_policy="en_lines"),
    "machines_odd": dict(
        ar="معدات ومكاين", pillar="satisfying", kinds=("short",),
        durations={"short": ["20s", "30s", "45s"]},
        scenes=["harmonograph", "stinger_glitch", "zen_garden"],
        audio=["room_tone", "cafe"], mood=["ميكانيكي", "مرضٍ", "دقيق"],
        palettes=["cool_slate", "paper_warm", "midnight"],
        montage=["لقطات ماكينة", "حركة دقيقة", "قطع على الإيقاع"],
        title_styles=["{kw} working perfectly is so satisfying", "The machine that never misses: {kw}",
                      "{kw} — oddly satisfying mechanics", "Watch {kw} do its thing"],
        desc_intro="{kw} — satisfying mechanics and precision in motion.",
        tags=["oddly satisfying", "machines", "engineering", "satisfying", "how it works", "timelapse",
              "factory", "precision"],
        playlist="Machines & Odd", dayparts={"midday": 4, "evening": 5, "morning": 4, "night": 3},
        hooks_en=["Satisfying", "Perfectly timed", "Wait for the last move"],
        thumb_styles=["ماكينة + نص", "أداة دقيقة + كلمة", "خلفية معدنية + إيموجي"],
        text_policy="en_lines"),
    "ocean_deep": dict(
        ar="أعماق البحر", pillar="satisfying", kinds=("short",),
        durations={"short": ["20s", "30s", "45s"]},
        scenes=["ocean_night", "beach_night", "valley_lake"],
        audio=["ocean", "waves"], mood=["عميق", "غامض", "هادي"],
        palettes=["deep_blue", "cool_slate", "midnight"],
        montage=["تحت الماء", "حركة ناعمة", "تفاصيل المرجان"],
        title_styles=["{kw} — the ocean is a different planet", "Real footage: {kw}",
                      "{kw} up close 🌊", "Nobody expects {kw} to look like this"],
        desc_intro="{kw} — real underwater footage. The deep sea never stops surprising.",
        tags=["ocean", "underwater", "sea life", "marine", "4k", "nature documentary", "fish",
              "deep sea"],
        playlist="Ocean & Wild", dayparts={"evening": 4, "night": 5, "midday": 3, "morning": 3},
        hooks_en=["Real footage 🌊", "You won't believe this is real", "Sound on"],
        thumb_styles=["سمكة + نص", "ماء أزرق + كلمة", "شعاب + إيموجي"],
        text_policy="facts"),
    "birds_wild": dict(
        ar="طيور وحياة برية", pillar="satisfying", kinds=("short",),
        durations={"short": ["20s", "30s", "45s"]},
        scenes=["forest_night", "valley_lake", "beach_night"],
        audio=["night_forest", "rain_soft"], mood=["طبيعي", "حي", "جميل"],
        palettes=["sunset_warm", "cool_slate", "deep_blue"],
        montage=["لقطات طيور", "تقريب", "إيقاع خفيف"],
        title_styles=["{kw} in slow motion is a masterpiece", "The sound {kw} makes at 4am 🐦",
                      "{kw} — nature's best design", "You've never seen {kw} like this"],
        desc_intro="{kw} — wildlife footage with natural sound. Nature does the editing.",
        tags=["birds", "wildlife", "nature", "animals", "birdwatching", "4k", "ornithology",
              "nature sounds"],
        playlist="Cute & Wild", dayparts={"morning": 5, "midday": 4, "evening": 3, "night": 3},
        hooks_en=["Sound on 🐦", "Nature's best", "Wait for the wings"],
        thumb_styles=["طير ملوّن + نص", "لقطة قريبة + كلمة", "غابة + إيموجي"],
        text_policy="en_lines"),
    "lights_bokeh": dict(
        ar="أضواء وبوكيه", pillar="satisfying", kinds=("short",),
        durations={"short": ["20s", "30s"]},
        scenes=["neon_rain", "candle_desk", "stinger_confetti"],
        audio=["room_tone", "calm_night"], mood=["ساحر", "لمّاع", "ليلي"],
        palettes=["neon_pop", "midnight", "warm_amber"],
        montage=["بوكيه", "خرج عن التركيز", "انتقالات ناعمة"],
        title_styles=["{kw} at night hits different ✨", "30 seconds of {kw}",
                      "{kw} — perfect background", "The prettiest {kw} you'll see today"],
        desc_intro="{kw} — light, bokeh and colour. A calm background for anything you're doing.",
        tags=["bokeh", "lights", "night", "aesthetic", "background", "neon", "satisfying", "calm"],
        playlist="Sky & Light", dayparts={"night": 5, "evening": 5, "midday": 2, "morning": 2},
        hooks_en=["Pure vibes ✨", "Watch the lights", "Background of the day"],
        thumb_styles=["بوكيه ملوّن + نص", "أضواء نيون + كلمة", "لمعة + إيموجي"],
        text_policy="en_lines"),
    "vintage_archive": dict(
        ar="أرشيف قديم", pillar="facts", kinds=("short",),
        durations={"short": ["20s", "30s", "45s"]},
        scenes=["train_window", "stinger_glitch", "library_rain"],
        audio=["room_tone", "cafe"], mood=["قديم", "حنين", "توثيقي"],
        palettes=["paper_warm", "cool_slate", "warm_amber"],
        montage=["فوتاج أرشيفي", "حبيبات فيلم", "إيقاع هادي"],
        title_styles=["{kw} — restored archive footage", "What {kw} looked like decades ago",
                      "{kw} in the archive (real footage)", "History in {dur}: {kw}"],
        desc_intro="{kw} — public-domain archive footage, lightly restored. Real people, real time.",
        tags=["archive", "history", "vintage", "old footage", "documentary", "public domain",
              "restored", "historical"],
        playlist="Archive & Facts", dayparts={"midday": 4, "evening": 4, "morning": 4, "night": 3},
        hooks_en=["Real archive footage", "Look how it changed", "From the archive"],
        thumb_styles=["فوتاج قديم + نص", "أبيض وأسود + كلمة", "لقطة أرشيف + إيموجي"],
        text_policy="facts"),
}
for _g, _v in _NEW.items():
    _v.setdefault("text_policy", "en_lines")
    GENRES[_g] = _v
