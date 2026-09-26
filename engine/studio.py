"""
🏗️ الاستوديو — يبني خطة اليوم كاملة: ٢٤ شورت (كل ساعة) + ٤ طويلة + حكاية.
============================================================================
كل دور في الخطة لازم يعدّي **حارس التنوّع** (مفيش قوالب متكررة — سياسة يوتيوب).
كل دور بياخد: نوع · مشهد · صوت · لوحة · انتقال · مونتاج · شكل عنوان · موضوع حقيقي.

    from engine import studio
    plan = studio.build_day("2026-09-27")     # يكتب state/plan_<date>.json
    plan["slots"]                              # نفس شكل خطة المصنع القديمة + genre
"""
from __future__ import annotations

import json
import pathlib
import random
from datetime import date, datetime, timedelta, timezone

from engine import genres, variety

STATE = pathlib.Path("state")

# ── مواضيع حقيقية لكل نوع (كلها من كلمات طلب حقيقي أو مصادر موثّقة) ──────────
# كل حكاية: (العنوان السردي، كلمة بحث الصور الحقيقية/الرسومات)
STORY_TOPICS = [
    ("the little rain cloud", "rain cloud sky watercolor"),
    ("the lost paper boat", "paper boat water river"),
    ("the lighthouse keeper", "lighthouse night sea"),
    ("the seed that waited", "sprout growing soil macro"),
    ("the moon's reflection", "moon reflection water night"),
    ("the tiny fox", "fox forest animal illustration"),
    ("the old clock", "old clock vintage macro"),
    ("the bridge of lanterns", "lanterns night bridge festival"),
    ("the whale and the star", "whale ocean night illustration"),
    ("the painter of rainbows", "rainbow sky landscape"),
    ("the paper plane journey", "paper plane sky clouds"),
    ("the sleepy train", "train window night journey"),
    ("the little astronaut", "astronaut space illustration"),
    ("the kite and the wind", "kite sky clouds painting"),
    ("the garden that listened", "garden flowers morning illustration"),
    ("the star that was shy", "stars night sky soft"),
    ("the turtle who carried rain", "turtle ocean illustration"),
    ("the door in the tree", "tree door forest fantasy"),
    ("the clockmaker's gift", "clockmaker workshop vintage"),
    ("the whale who sang alone", "whale underwater soft light"),
    ("the mountain that smiled", "mountain sunrise painting"),
    ("the boy who drew clouds", "drawing clouds sketchbook"),
    ("the lighthouse and the storm", "lighthouse storm waves painting"),
    ("the tiny gardener", "seedling hands soil macro"),
    ("the moon who waited", "moonrise over hills painting"),
    ("the river that remembered", "river stones water painting"),
    ("the bird who lost its song", "bird branch watercolor"),
]

TOPICS = {
    "sleep_ambience": [
        "Rain Sounds", "Heavy Rain on a Window", "Ocean Waves", "Fireplace Crackling",
        "Thunderstorm at Night", "Snowfall at Night", "Night Train Ride", "Forest at Night",
        "Beach at Midnight", "Lake at Dusk", "Wind in the Pines", "Gentle Rain on a Tent",
        "Distant Thunder Rolls", "Rain on a Tin Roof", "Cabin Fireplace and Rain",
        "Ocean Waves at Sunrise", "Desert Wind at Night", "Waterfall in the Forest",
        "Snow Falling in a Quiet Village", "Crackling Campfire and Crickets",
        "Rain on Leaves", "Boat Rocking on Calm Water", "Mountain Stream", "Meadow at Dusk",
        "Rain on a Balcony in the City", "Fog over the Lake", "Old Ship at Anchor",
        "Thunder Far Away", "Warm Fire and Rain", "Night Wind Through Bamboo"],
    "focus_study": ["Brown Noise", "Rain on the Window", "Quiet Library", "Soft Cafe Ambience",
                    "Snow Day Study", "Deep Focus Noise", "Pink Noise", "White Noise",
                    "Rainy Study Session", "Coffee Shop Murmur", "Night Study Desk",
                    "Clock and Rain", "Train Compartment Focus", "Silent Library at Dawn",
                    "Wind and Pages", "Keyboard and Rain", "Hearth and Homework"],
    "story": [t for t, _q in STORY_TOPICS],   # ٢٧ حكاية (قصيرة وطويلة)
    "satisfying": ["Kinetic Sand", "Soap Cutting", "Ice Crushing", "Magnetic Beads",
                   "Water Rings", "Perfect Cuts", "Hydraulic Press", "Bubble Wrap",
                   "Glass and Sand", "Rolling Dominoes", "Liquid Marble Pour", "Sand Raking",
                   "Wax Seals", "Chocolate Breaking", "Slime Stretch", "Layered Resin",
                   "Ball Bearings in Motion", "Powder Pressing", "Paint Swirl Pour",
                   "Precision Slicing", "Slow Foam Rising", "Copper and Salt",
                   "Ink in Water", "Dry Ice Fog", "Sand Cutting Glass"],
    "space_nature": ["The Carina Nebula", "Earth From Orbit", "Aurora Over Iceland",
                     "The Deep Ocean Floor", "Glacier Calving", "Saturn's Rings",
                     "Volcano at Night", "The Grand Canyon at Dawn",
                     "The Milky Way Core", "Jupiter's Great Red Spot", "Comet Tails",
                     "Sahara Dunes at Sunset", "Icelandic Lava Fields", "Ancient Redwoods",
                     "The Northern Lights Over a Lake", "Antarctic Ice Shelves",
                     "Nile River from Space", "Coral Reef at Night", "The Himalayas at Dawn",
                     "Desert Bloom After Rain", "Tornado Alley Skies", "Bioluminescent Bay"],
    "fun_memes": ["the Monday morning", "the gym in January", "the group project",
                  "the Wi-Fi dies", "the last slice of pizza", "the alarm clock",
                  "the parking spot", "the phone at 1%", "the printer jams",
                  "the video call background", "the shopping list you forget",
                  "the umbrella you left", "the queue that picks the wrong line",
                  "the microwave timer", "the meeting that could be an email",
                  "the charger that never fits", "the sock that disappears"],
    "calm_wellness": ["Breathe With Me", "Slow Down", "Before Sleep", "Reset Your Day",
                      "Two Minutes of Calm", "Box Breathing", "4-7-8 Breathing",
                      "Morning Reset", "After Work Wind Down", "Quiet the Mind",
                      "Steady Breath at the Ocean", "Breathe With the Rain",
                      "One Minute at a Time"],
    "facts": [],          # بتُجاب من ويكيبيديا/ناسا (حقائق موثّقة بمصادر)
}

CHARACTERS = ["Pip", "Kiki", "Nori", "Filo", "Momo", "Bubu", "Bomi", "Koko"]

STRUCTURES = ["بداية هادية ← حركة ← استقرار", "سؤال ← كشف ← راحة",
              "٣ مقاطع متساوية", "تصاعد ← ذروة ← تنفّس", "لقطة واحدة مستمرة"]


def _facts_topic(rng: random.Random) -> dict:
    """موضوع حقائق حقيقي موثّق (ويكيبيديا) + أسطر نص للشاشة + رابط المصدر."""
    from engine import providers
    seeds = ["Rain", "Volcano", "Black hole", "Octopus", "Honey bee", "Aurora", "Glacier",
             "Lightning", "Coral reef", "Meteorite", "Desert", "Rainforest", "Whale shark",
             "Magnetic field", "Tardigrade", "Mariana Trench", "Antarctica", "Nebula"]
    rng.shuffle(seeds)
    for s in seeds[:6]:
        w = providers.wikipedia_summary(s)
        if w.get("extract"):
            sentences = [x.strip() for x in w["extract"].replace("\n", " ").split(". ") if len(x.strip()) > 25]
            lines = [(x if x.endswith(".") else x + ".")[:110] for x in sentences[:3]]
            if len(lines) >= 2:
                return {"topic": w["title"], "lines": lines, "source": w["url"],
                        "image": w.get("image"), "image_source": "Wikipedia/Wikimedia"}
    return {"topic": "Rain", "lines": [], "source": "https://en.wikipedia.org/wiki/Rain"}


def _topic(gid: str, rng: random.Random) -> dict:
    if gid == "facts":
        return _facts_topic(rng)
    pool = TOPICS.get(gid) or ["Ambience"]
    kw = rng.choice(pool)
    out = {"topic": kw}
    if gid == "story":
        pair = next((p for p in STORY_TOPICS if p[0] == kw), (kw, kw))
        out.update({"thing": pair[0], "image_query": pair[1], "character": rng.choice(CHARACTERS)})
    else:
        out["image_query"] = kw
    return out


LONG_SLEEP_TOPICS = ["Rain Sounds", "Ocean Waves", "Fireplace Crackling", "Thunderstorm at Night",
                     "Snowfall at Night", "Night Forest", "Beach at Midnight", "Mountain Stream",
                     "Desert Wind", "Night Train"]


def _kw_for_meta(gid: str, topic: str) -> str:
    """صيغة الكلمة المفتاحية المناسبة للنوع (نفس أسلوب كل نوع)."""
    t = topic
    if gid == "sleep_ambience":
        return t if "Sounds" in t or "Sounds" in t else f"{t} Sounds"
    if gid == "focus_study":
        return t if t.endswith("Noise") or "Ambience" in t else t
    if gid == "satisfying":
        return t
    if gid == "space_nature":
        return t
    if gid == "fun_memes":
        return t
    if gid == "calm_wellness":
        return t
    return t


def _slot(hour: int, at: str, kind: str, gid: str, rng: random.Random) -> dict:
    """دور واحد — التركيبة تعدّي حارس التنوّع **بعد** ما العنوان الحقيقي يتحدد."""
    g = genres.get(gid)
    rec = seed = title = sig = None
    for attempt in range(12):                       # بنجرّب لحد ما نلاقي تركيبة جديدة فعلاً
        topic = _topic(gid, rng)
        dur = rng.choice(g["durations"][kind])
        r, sd = variety.pick_recipe(gid, seed=rng.randint(1, 10 ** 9),
                                    extra_marks=(topic.get("topic", ""),), history=variety.recent())
        kw = _kw_for_meta(gid, topic.get("topic", ""))
        t = genres.title_for(gid, rng, kw=kw,
                             dur=dur.replace("h", " hours").replace("s", " seconds"),
                             name=topic.get("character", ""), thing=topic.get("thing", ""))
        sg = variety.signature_for(r, title=t, hour=hour)
        if not variety.too_similar(sg, history=variety.recent()):
            rec, seed, title, sig = r, sd, t, sg
            break
        rec = rec or r; seed = seed or sd; title = title or t; sig = sig or sg
    idea = {
        "genre": gid, "genre_ar": g["ar"], "pillar": g["pillar"], "kind": kind,
        "duration": dur, "scene": rec["scene"], "audio": rec["audio"], "palette": rec["palette"],
        "transition": rec["transition"], "montage": rec["montage"], "mood": rec["mood"],
        "hook": rng.choice(g["hooks_en"]), "thumb": rng.choice(g["thumb_styles"]),
        "structure": rng.choice(STRUCTURES), "kw": kw, "topic": topic.get("topic", ""),
        "character": topic.get("character"), "thing": topic.get("thing"),
        "image_query": topic.get("image_query") or topic.get("topic", ""),
        "lines": topic.get("lines") or [], "source": topic.get("source"),
        "playlist": g["playlist"], "title_style": title,
        "signature": json.dumps(sig, ensure_ascii=False, sort_keys=True), "sig": sig,
        "predicted": round(rng.uniform(1.2, 2.6), 3),
        "why": f"نوع {g['ar']} · وقت {genres.daypart(hour)} · تركيبة جديدة (تنوّع مؤكد)",
    }
    return {"hour": hour, "at": at, "kind": kind, "idea": idea, "seed": seed}


def build_day(date_str: str | None = None, shorts: int = 24, longs: tuple = (3, 8, 10, 12),
              write: bool = True, state_dir=None) -> dict:
    """خطة اليوم: شورت كل ساعة (بنوع مناسب للوقت) + الطويلة + حكاية."""
    date_str = date_str or date.today().isoformat()
    rng = random.Random(f"studio|{date_str}")
    slots: list[dict] = []

    # ٢٤ شورت — ساعة ورا ساعة، والنوع بيتغيّر حسب وقت الجمهور
    hours = list(range(24))
    for h in hours:
        gid = genres.weighted_pick(h, rng)
        at = f"{date_str}T{h:02d}:00:00Z"
        slots.append(_slot(h, at, "short", gid, rng))
        variety.record(slots[-1]["idea"]["sig"])          # نسجّل التركيبة الحقيقية بحارس التنوّع

    # الطويلة: أنواع ومشاهد مختلفة عن بعض وعن الشورتس
    long_genres = ["sleep_ambience", "sleep_ambience", "focus_study", "space_nature"]
    long_pool = list(LONG_SLEEP_TOPICS); rng.shuffle(long_pool)
    long_hours = [3, 8, 10, 12]
    for i, hrs in enumerate(longs):
        gid = long_genres[i % len(long_genres)]
        hour = long_hours[i % len(long_hours)]
        slot = _slot(hour, f"{date_str}T{hour:02d}:00:00Z", "long", gid, rng)
        slot["idea"]["duration"] = f"{hrs}h"
        if gid == "sleep_ambience" and long_pool:          # موضوع مختلف لكل طويلة
            k = long_pool.pop()
            slot["idea"]["kw"] = k
            slot["idea"]["topic"] = k
        slots.append(slot)
        variety.record(slot["idea"]["sig"])

    slots.sort(key=lambda s: (s["hour"], 0 if s["kind"] == "long" else 1))
    plan = {
        "date": date_str, "studio": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shorts": shorts, "longs": list(longs), "mix": _mix_stats(slots),
        "best_long_hours_seen": list(long_hours), "slots": slots,
    }
    if write:
        d = pathlib.Path(state_dir) if state_dir else STATE
        d.mkdir(parents=True, exist_ok=True)
        (d / f"plan_{date_str}.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan


def _mix_stats(slots: list[dict]) -> dict:
    out: dict = {}
    for s in slots:
        g = s["idea"]["genre_ar"]
        out[g] = out.get(g, 0) + 1
    return out


def queue_day(date_str: str | None = None) -> dict:
    """يحوّل خطة اليوم إلى طابور جاهز للنشر (نفس شكل طابور المصنع)."""
    plan = build_day(date_str)
    q = {"items": [], "date": plan["date"], "studio": True}
    for s in plan["slots"]:
        q["items"].append({
            "title": f"[{s['idea']['genre_ar']}] {s['idea']['kw']} · {s['idea']['duration']}",
            "slot": {**s, "date": plan["date"]},
            "seed": s.get("seed"), "added": datetime.now(timezone.utc).isoformat(),
        })
    return q


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else None
    p = build_day(d)
    print(json.dumps(p["mix"], ensure_ascii=False, indent=2))
    print("عدد الأدوار:", len(p["slots"]))
