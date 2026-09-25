"""
🧠 العقل الذاتي — Dollars Studio
================================
الوكيل الذكي اللي **بيتابع وبيتعلّم وبيطوّر نفسه**:
- بيراقب أداء كل فيديو (مشاهدات · نسبة استمرار · تفاعل) ويحدّث أوزان كل خصلة.
- بيولّد أفكار جديدة من تركيبة (شخصية × عالم × بنية × خطّاف) ويرتّبها بتوقّع الأداء.
- بيخترع **شخصيات جديدة** (أسماء من مقاطع + صفات + عوالم + برومبت صورة).
- بيبني **جدول اليوم** (شورت كل ساعة + الطويلات 4/6/8/12) من غير أي تدخّل.
- بيعدّل **معدّلات تعلّمه بنفسه** (self-tuning): لو التوقّع غلط بسرعة يتعلّم أسرع،
  ولو مستقر يهدّي ويستثمر أكتر في الفايزين.

مفيش سحر ومفيش كلام كبير: ده تعلّم إحصائي حقيقي من أرقام القناة.
لو مفيش أرقام لسه (القناة لسه ما اتنشرتش) بيشتغل على «قَبْليات» من بحثنا
(docs/RESEARCH_2026-09.md) وبيفضل يتعلّم أول ما الأرقام توصل.

الواجهة:
    brain = agent.Brain.load()
    fresh = agent.collect_ideas(brain, n=20)      # أفكار مرتّبة
    chars = agent.spawn_characters(brain, n=3)    # شخصيات جديدة
    plan  = agent.plan_day(brain, date_str)       # جدول اليوم
    agent.learn(brain, "state/analytics.json")    # تعلّم من الأرقام
    print(agent.daily_report(brain, plan, fresh))
"""
from __future__ import annotations

import json
import math
import pathlib
import random
import statistics
from datetime import date, datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
CONTENT = ROOT / "content"

# ───────────────────────── خصائص المحتوى (اللي بنتعلّم منها) ─────────────────────────

PILLARS = {
    "sleep": {"share": 0.35, "longs_per_day": 3, "scenes": ["black", "rain_glass", "ocean", "starfield", "aurora", "fireplace",
                                                            "valley_lake", "dunes_moon", "snow_pines"],
              "audio": ["sleep_rain", "rain_only", "ocean", "storm", "fireplace", "calm_night", "focus"],
              "dur_h": [3, 8, 10]},
    "story": {"share": 0.25, "longs_per_day": 0, "scenes": ["sand_table", "harmonograph", "starfield", "planet_rings"],
              "audio": [], "dur_min": [1, 2, 3, 4]},
    "satisfying": {"share": 0.35, "longs_per_day": 0,
                   "scenes": ["sand_table", "pendulum_wave", "harmonograph", "planet_rings", "stinger_confetti",
                              "stinger_glitch", "stinger_zoom", "stinger_ink"],
                   "audio": [], "dur_s": [15, 30, 45, 60]},
    "focus": {"share": 0.05, "longs_per_day": 3, "scenes": ["black", "rain_glass", "starfield"],
              "audio": ["focus", "calm_night"], "dur_h": [2, 3, 4]},
}

HOOKS = ["سؤال في أول ثانية", "صوت مفاجئ", "قبل/بعد", "لقطة قريبة جدًا", "حركة كاميرا سريعة",
         "لون غريب", "ظهور شخصية", "عدّاد", "حركة عكسية", "مقارنة", "همسة", "صمت مفاجئ"]

STRUCTURES = {
    "sleep": ["بداية هادية ← ثبات", "مطر ← رعد ← هدوء", "مشهد ليلي ← نجوم"],
    "story": ["مشكلة ← محاولة ← حل", "خوف ← شجاعة ← مكافأة", "صداقة ← عقبة ← لقاء",
              "لقى كنز ← خسره ← لقى أحسن"],
    "satisfying": ["حركة واحدة كاملة", "تراكم ← ذروة ← تنظيف", "دورات متكرّرة مريحة",
                   "مقارنة سرعات", "نمو نمط هندسي"],
    "focus": ["بداية هادية ← ثبات", "ضجيج أبيض ← تركيز"],
}

THUMB_STYLES = ["شخصية كبيرة + سطر قصير", "مشهد طبيعي + رقم مدة", "شاشة سوداء + نص واضح",
                "لمعة/لمعان مركزي", "وش متعجّب", "قبل/بعد مقسوم"]

TITLE_PATTERNS = {
    "sleep": ["{kw} for Sleeping | {dur} Hours Black Screen", "{kw} • {dur} Hours • Deep Sleep",
              "Sleep in 3 Minutes: {kw} ({dur} Hours)", "{kw} {dur}H — No Music, Just {kw}"],
    "story": ["{name} and the {thing} — a wordless story", "The {thing} | {name}'s little tale",
              "{name} learns to {verb} (wordless animation)"],
    "satisfying": ["{kw} — oddly satisfying", "{kw} in {dur} seconds", "perfect {kw} #shorts"],
    "focus": ["{kw} for Studying | {dur} Hours", "Deep Focus: {kw} ({dur}H)"],
}

LANGS = {"ar": "العربية", "en": "English", "es": "Español", "pt": "Português", "hi": "हिन्दी",
         "id": "Bahasa Indonesia", "de": "Deutsch", "fr": "Français", "tr": "Türkçe", "ru": "Русский"}


def _jload(p: pathlib.Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _jdump(p: pathlib.Path, obj) -> pathlib.Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ───────────────────────────── العقل ─────────────────────────────

class Brain:
    """أوزان لكل خصلة + معدّلات تتظبّط لوحدها + سجل تعلّم."""

    VERSION = 3

    def __init__(self, weights=None, counts=None, meta=None, history=None, seen=None, characters_seen=None):
        self.weights = weights or {}
        self.counts = counts or {}
        self.meta = meta or {
            "lr": 0.25, "eps": 0.15, "blend": {"views": 0.55, "retention": 0.30, "engage": 0.15},
            "samples": 0, "baseline": None, "last_error": None, "pred_errors": [],
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self.history = history or []          # كل تجربة اتعلّمنا منها (مشاهدات · استمرار · تفاعل)
        self.seen = seen or []                # بصمات الأفكار اللي اتستخدمت (منع التكرار)
        self.characters_seen = characters_seen or []

    # ── تقدير ──
    def prior(self, dim: str, opt: str) -> float:
        return float(self.weights.get(dim, {}).get(str(opt), 1.0))

    def n(self, dim: str, opt: str) -> int:
        return int(self.counts.get(dim, {}).get(str(opt), 0))

    def score(self, features: dict) -> float:
        """توقّع الأداء = متوسط أوزان الخصال (وزن أعلى = المتوقع أفضل)."""
        vals = [self.prior(d, o) for d, o in features.items() if o is not None]
        if not vals:
            return 1.0
        return float(statistics.fmean(vals))

    def ucb(self, features: dict, total: int, c: float = 0.8) -> float:
        """اختيار يوازن الاستغلال والاستكشاف (الخصائص الجديدة تاخد فرصة عادلة)."""
        out = []
        for d, o in features.items():
            if o is None:
                continue
            n = self.n(d, o)
            bonus = c * math.sqrt(math.log(max(total, 2)) / max(n, 1)) * (0.0 if n else 1.0)
            out.append(self.prior(d, o) + bonus)
        return float(statistics.fmean(out)) if out else 1.0

    # ── تعلّم ──
    @staticmethod
    def outcome_score(rec: dict, blend: dict) -> float:
        views = max(0.0, float(rec.get("views", 0)))
        ret = float(rec.get("retention", 0.35))          # نسبة الاستمرار (0..1)
        eng = (float(rec.get("likes", 0)) + 2.0 * float(rec.get("comments", 0))
               + 3.0 * float(rec.get("subs", 0))) / max(views, 1.0)
        v = math.log10(1.0 + views) / 7.0                # 10^7 مشاهدات = 1.0
        score = blend["views"] * v + blend["retention"] * ret + blend["engage"] * min(eng * 50.0, 1.0)
        return float(max(score, 1e-4))

    def observe(self, rec: dict) -> float:
        """
        تجربة واحدة: بنقارن أداء الفيديو ده بمتوسط أدائنا (baseline) — الأفضل من المتوسط
        بيرفع أوزان خصاله، والأقل بيوطّيها. (تعلّم نسبي ⇒ مفيش مشاكل بمقاس الأرقام.)
        """
        feats = rec.get("features") or {}
        if not feats:
            return 0.0
        score = self.outcome_score(rec, self.meta["blend"])
        base = self.meta.get("baseline")
        if base is None:
            base = score
        base = 0.92 * float(base) + 0.08 * score          # متوسط متحرّك (بيواكب تغيّر الجمهور)
        self.meta["baseline"] = base
        perf = score / (2.0 * base + 1e-6)                # 0.5 = أداء متوسط بالظبط
        target = 1.0 + (perf - 0.5)
        pred = self.score(feats)
        err = target - pred                               # خطأ التوقّع (للضبط الذاتي)
        lr = float(self.meta["lr"])
        for d, o in feats.items():
            if o is None:
                continue
            w = self.prior(d, str(o))
            n = self.n(d, str(o))
            adapt = lr / (1.0 + 0.25 * n)                 # كل ما شفناه أكتر، تحديث أهدى
            nw = w + adapt * (perf - 0.5) * 2.0
            self.weights.setdefault(d, {})[str(o)] = float(min(max(nw, 0.40), 2.50))
            self.counts.setdefault(d, {})[str(o)] = n + 1
        self.meta["samples"] = int(self.meta.get("samples", 0)) + 1
        self.history.append({"at": datetime.now(timezone.utc).isoformat(), "score": round(score, 4),
                             "perf": round(perf, 4), "pred": round(pred, 4), "err": round(err, 4),
                             "views": rec.get("views"), "title": rec.get("title"),
                             "features": feats})
        self.history = self.history[-500:]
        self._selftune(err)
        return err

    def _selftune(self, err: float) -> None:
        """تطوير ذاتي: يعدّل معدّل التعلّم والاستكشاف حسب دقّة توقّعاته."""
        errs = self.meta.setdefault("pred_errors", [])
        errs.append(abs(err)); del errs[:-50]
        self.meta["last_error"] = round(err, 4)
        if len(errs) >= 8:
            mae = statistics.fmean(errs[-8:])
            self.meta["lr"] = float(min(max(self.meta["lr"] * (1.15 if mae > 0.25 else 0.90), 0.05), 0.9))
            # لو الخطأ كبير ⇒ استكشاف أكتر (يمكن إحنا غلط في فهم الجمهور)
            self.meta["eps"] = float(min(max(0.10 + mae, 0.05), 0.45))

    # ── مزامنة ──
    def save(self, path=None):
        p = pathlib.Path(path or STATE / "brain.json")
        _jdump(p, {"version": self.VERSION, "weights": self.weights, "counts": self.counts,
                   "meta": self.meta, "history": self.history, "seen": self.seen,
                   "characters_seen": self.characters_seen})
        return p

    @classmethod
    def load(cls, path=None):
        d = _jload(pathlib.Path(path or STATE / "brain.json"), None)
        if not d:
            b = cls()
            b._bootstrap()
            return b
        return cls(d.get("weights"), d.get("counts"), d.get("meta"), d.get("history"),
                   d.get("seen"), d.get("characters_seen"))

    def _bootstrap(self):
        """قَبْليات من البحث: اللي عرفناه من يوتيوب قبل أول فيديو."""
        # القَبْليات من البحث (평균 = 1.0): كل قيمة أعلى من 1 = متوقّع أحسن من المتوسط
        priors = {
            "pillar": {"sleep": 1.15, "satisfying": 1.08, "story": 1.02, "focus": 0.95},
            "scene": {"black": 1.18, "rain_glass": 1.12, "ocean": 1.06, "fireplace": 1.06,
                      "starfield": 1.02, "aurora": 1.00, "sand_table": 1.06,
                      "pendulum_wave": 1.02, "harmonograph": 1.00},
            "duration": {"10h": 1.18, "8h": 1.12, "4h": 1.06, "3h": 1.06, "2h": 1.00,
                         "60s": 1.05, "30s": 1.08, "15s": 1.00, "45s": 0.98, "2m": 0.98, "1m": 1.00},
            "hook": {"سؤال في أول ثانية": 1.05, "صوت مفاجئ": 1.04, "قبل/بعد": 1.03},
            "thumb": {"شاشة سوداء + نص واضح": 1.15, "مشهد طبيعي + رقم مدة": 1.08,
                      "شخصية كبيرة + سطر قصير": 1.10},
            "hour": {str(h): (1.08 if h in (21, 22, 23, 0, 1, 2) else (0.97 if h in (3, 4, 5) else 1.0))
                     for h in range(24)},
        }
        self.weights = priors
        self.counts = {d: {k: 0 for k in v} for d, v in priors.items()}

    # ── تقرير ──
    def winners(self, k: int = 8) -> list:
        rows = []
        for d, opts in self.weights.items():
            for o, w in opts.items():
                if self.n(d, o) > 0 or d in ("pillar", "duration", "thumb"):
                    rows.append((d, o, float(w), self.n(d, o)))
        rows.sort(key=lambda r: (-r[2], -r[3]))
        return rows[:k]


# ───────────────────────────── توليد الأفكار ─────────────────────────────

def _kw(pillar: str, rng: random.Random) -> str:
    return {
        "sleep": rng.choice(["Rain Sounds", "Thunderstorm", "Ocean Waves", "Fireplace Crackling",
                             "Night Forest Rain", "Heavy Rain on Window"]),
        "satisfying": rng.choice(["Kinetic Sand Cutting", "Pendulum Wave", "Sand Drawing Table",
                                  "Hypnotic Lissajous", "Color Sand Layers"]),
        "story": rng.choice(["Paper Man", "Little Clay Ball", "Cloud Cat"]),
        "focus": rng.choice(["Brown Noise", "Rain", "White Noise", "Deep Space Ambience"]),
    }[pillar]


def collect_ideas(brain: Brain, n: int = 20, pillar: str | None = None, date_str: str | None = None,
                  characters: list | None = None) -> list:
    """يولّد أفكار جديدة مرتّبة بتوقّع الأداء — ومفيش تكرار لما اتعمل قبل كده."""
    rng = random.Random(f"{date_str or date.today().isoformat()}|{brain.meta.get('samples', 0)}")
    chars = characters if characters is not None else (load_characters().get("characters") or [])
    seen = set(brain.seen)
    out = []
    total = max(brain.meta.get("samples", 0), 1)
    guard = 0
    while len(out) < n and guard < n * 25:
        guard += 1
        p = pillar or rng.choices(list(PILLARS), weights=[PILLARS[k]["share"] for k in PILLARS])[0]
        spec = PILLARS[p]
        scene = rng.choice(spec["scenes"])
        structure = rng.choice(STRUCTURES[p])
        hook = rng.choice(HOOKS)
        thumb = rng.choice(THUMB_STYLES)
        if p in ("sleep", "focus"):
            if rng.random() < 0.35:                  # شورت أجواء من نفس النمط
                dur = f"{rng.choice([45, 60])}s"
                ch = None
                kind = "short"
            else:
                dur = rng.choice([f"{h}h" for h in spec["dur_h"]])
                ch = None
                kind = "long"
        elif p == "story":
            dur = f"{rng.choice(spec['dur_min'])}m"
            ch = rng.choice(chars)["id"] if chars else None
            kind = "long" if rng.random() < 0.5 else "short"      # قصة قصيرة كمان كل يوم
        else:
            dur = f"{rng.choice(spec['dur_s'])}s"
            ch = rng.choice(chars)["id"] if (chars and rng.random() < 0.25) else None
            kind = "short"
        feats = {"pillar": p, "scene": scene, "duration": dur, "hook": hook, "thumb": thumb,
                 "structure": structure, "kind": kind,
                 "hour": str(rng.choice([21, 22, 23, 0, 1, 2, 7, 8, 12, 18, 19, 20]))}
        sig = "|".join(f"{k}={v}" for k, v in sorted(feats.items()))
        if sig in seen:
            continue
        seen.add(sig)
        pred = brain.ucb({k: v for k, v in feats.items() if k != "hour"}, total)
        out.append({
            "signature": sig,
            "pillar": p, "kind": kind, "duration": dur, "scene": scene, "structure": structure,
            "hook": hook, "thumb": thumb, "hour": int(feats["hour"]), "character": ch,
            "predicted": round(pred, 3),
            "why": f"لأن {p} و{dur} و{thumb} أوزانهم أعلى عندنا دلوقتي",
            "sfx": [] if p in ("sleep", "focus") else ["whoosh", "sparkle", "boing"],
            "status": "idea",
        })
    out.sort(key=lambda x: -x["predicted"])
    brain.seen = list(seen)[-3000:]
    return out


# ───────────────────────────── شخصيات جديدة ─────────────────────────────

SYL_A = ["ki", "lu", "mo", "ta", "zi", "bo", "na", "ri", "du", "pe", "wa", "shu", "gri", "la", "mi"]
SYL_B = ["no", "ta", "mi", "ro", "la", "ka", "zo", "va", "shi", "nu", "bi", "po", "ma", "ri"]
TYPES = [("كائن طيني صغير", "a small clay creature", "طين ناعم + عينين كبيرتين"),
         ("قطة سحابية", "a tiny cloud cat", "سحابة ناعمة + ذيل نجوم"),
         ("روبوت ورق", "a tiny paper robot", "ورق مطبّق + مفصلات"),
         ("نبتة فضائية", "a tiny space plant", "ساق ضوئية + أوراق شفافة"),
         ("سمكة نجمية", "a little star fish", "جسم لامع + زعانف ضوء"),
         ("كائن ضبابي", "a misty creature", "جسم بخار + عيون ناعمة"),
         ("فراشة زجاجية", "a glass butterfly", "أجنحة شفافة + خطوط ضوء"),
         ("قطة صحراوية", "a desert kitten", "فرو رملي + عيون ذهبية"),
         ("حجر ودود", "a friendly stone", "حجر أملس + وجه بسيط"),
         ("تمساح صغير جدًا", "a tiny friendly crocodile", "حراشف باهتة + عيون كبيرة")]
WORLDS = ["kitchen", "space", "rain", "ocean", "night_sky", "bedroom", "forest", "desert",
          "clouds", "paper_world", "snow", "city_night", "garden", "moon"]
TRAITS = ["فضولي جدًا", "خجول بس شجاع", "دائمًا جعان", "بيحب يساعد", "كسول ومضحك",
          "بيخاف من الظل", "بيرتّب كل حاجة", "بيحب النجوم", "متسرّع ويقع", "هادي وبيفكّر"]
FORMATS = ["silent_gag", "minute_story", "calm_loop", "whisper_bedtime", "tiny_adventure"]
BLOCK = {"mina", "nora", "sara", "adam", "mickey", "elsa", "batman", "pikachu", "sonic",
         "nemo", "shrek", "hello kitty", "pokemon", "disney"}


def _dist(a: str, b: str) -> int:
    """مسافة تحرير بسيطة (لمنع تشابه الأسماء)."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def spawn_characters(brain: Brain, n: int = 3, path=None) -> list:
    """يخترع شخصيات جديدة (اسم · شكل · صفة · عالم · برومبت صورة) — أصلية 100%."""
    rng = random.Random(brain.meta.get("samples", 0) * 7 + int(datetime.utcnow().timestamp()) % 100000)
    data = load_characters(path)
    chars = list(data.get("characters") or [])
    names = [c["name"] for c in chars] + list(brain.characters_seen)
    made = []
    for _ in range(n):
        for _try in range(500):
            nm = rng.choice(SYL_A).capitalize() + rng.choice(SYL_B)
            low = nm.lower()
            if low in BLOCK or any(_dist(low, x.lower()) < 3 for x in names):
                continue
            break
        typ_ar, typ_en, look_en = rng.choice(TYPES)
        world = rng.choice(WORLDS)
        trait = rng.choice(TRAITS)
        fmt = rng.choice(FORMATS)
        ch = {
            "id": f"{low}_auto",
            "name": nm,
            "type": typ_ar,
            "look": f"{look_en} — عيون كبيرة، بلا أي شبه بأي شخص حقيقي أو شخصية محمية",
            "personality": trait,
            "voice": "همهمات وبلا كلمات (يتفهم من غير لغة)",
            "worlds": [world, rng.choice(WORLDS)],
            "formats": [fmt, rng.choice(FORMATS)],
            "audience": "كل الأعمار — بصري 100%",
            "origin": "auto",
            "created": datetime.now(timezone.utc).isoformat(),
            "image_prompt": (f"cute original 2D animation character, {typ_en}, {look_en}, "
                             f"{world} background, soft warm lighting, flat vector style, "
                             f"clean silhouette, no text, original design, not resembling any "
                             f"existing brand character"),
        }
        names.append(nm)
        made.append(ch)
    if made:
        chars.extend(made)
        data["characters"] = chars
        data["_auto_count"] = sum(1 for c in chars if c.get("origin") == "auto")
        _jdump(pathlib.Path(path or CONTENT / "characters.json"), data)
    brain.characters_seen = (brain.characters_seen + [c["name"] for c in made])[-500:]
    return made


def load_characters(path=None) -> dict:
    return _jload(pathlib.Path(path or CONTENT / "characters.json"), {"characters": []}) or {"characters": []}


# ───────────────────────────── تعلّم من الأرقام ─────────────────────────────

def learn(brain: Brain, analytics_path="state/analytics.json") -> dict:
    """
    يقرأ أرقام القناة الحقيقية (مشاهدات · استمرار · تفاعل) وحدّث العقل.
    شكل الملف: {"videos":[{"title":..,"views":..,"retention":..,"likes":..,"comments":..,
                "subs":..,"features":{...}}]}
    """
    p = pathlib.Path(analytics_path)
    if not p.exists():
        return {"learned": 0, "note": "لسه مفيش أرقام — العقل شغال على القَبْليات لحد أول نشر"}
    d = _jload(p, {}) or {}
    vids = d.get("videos") or []
    errs = [brain.observe(v) for v in vids]
    return {"learned": len(vids), "mean_abs_error": round(statistics.fmean([abs(e) for e in errs]), 4) if errs else None,
            "lr": round(brain.meta["lr"], 3), "eps": round(brain.meta["eps"], 3)}


# ───────────────────────────── جدول اليوم ─────────────────────────────

def plan_day(brain: Brain, date_str: str | None = None, characters: list | None = None) -> dict:
    """24 شورت (كل ساعة) + الطويلات بفواصل 4/6/8/12 ساعة — كل حاجة متولّدة من الأوزان."""
    date_str = date_str or date.today().isoformat()
    d0 = datetime.fromisoformat(date_str + "T00:00:00")
    ideas = collect_ideas(brain, n=90, date_str=date_str, characters=characters)
    shorts = [i for i in ideas if i["kind"] == "short"]
    longs = [i for i in ideas if i["kind"] == "long"]
    # ── تنويع الشورتس: مش كله نمط واحد — توزيع حسب أوزان العقل مع ضمان حصص دنيا
    by_p = {}
    for i in shorts:
        by_p.setdefault(i["pillar"], []).append(i)
    mix_goal = {"satisfying": 14, "story": 5, "sleep": 3, "focus": 2}   # 24 ساعة/يوم
    # لو مفيش أفكار كفاية لنمط، الرحمة للنمط اللي عنده مخزون
    fallback_order = sorted(by_p, key=lambda k: -len(by_p[k]))
    rotation = []
    for pname, want in mix_goal.items():
        pool = by_p.get(pname) or by_p.get(fallback_order[0] if fallback_order else "", [])
        for k in range(want):
            if pool:
                rotation.append(pool[k % len(pool)])
    while len(rotation) < 24 and fallback_order:          # كمّل من أكبر نمط لو ناقص
        for pname in fallback_order:
            if len(rotation) >= 24:
                break
            rotation.append(by_p[pname][len(rotation) % len(by_p[pname])])
    rng_plan = random.Random(f"{date_str}|mix")
    rng_plan.shuffle(rotation)                            # نوزّع الأنماط على الساعات
    slots = []
    for h in range(24):
        pick = rotation[h % max(len(rotation), 1)] if rotation else None
        slots.append({"hour": h, "at": (d0 + timedelta(hours=h)).isoformat() + "Z",
                      "kind": "short", "idea": pick})
    # ── الطويلات: نوم/تركيز + قصة واحدة على الأقل كل يوم
    story_ideas = [i for i in longs if i["pillar"] == "story"]
    sleep_ideas = [i for i in longs if i["pillar"] != "story"]
    long_hours = [2, 8, 14, 20]          # فواصل 6 ساعات (مقسومة 12/6) — تتظبّط لو الأرقام قالت غير كده
    scores = sorted((brain.prior("hour", h), h) for h in range(24))
    best_long_hours = sorted([h for _, h in scores[-6:]])
    plan_longs = (sleep_ideas[:3] + story_ideas[:1]) if story_ideas else sleep_ideas[:4]
    for i, h in enumerate(sorted(set([long_hours[i % len(long_hours)] for i in range(len(long_hours))]))):
        if i < len(plan_longs):
            slots.append({"hour": h, "at": (d0 + timedelta(hours=h)).isoformat() + "Z",
                          "kind": "long", "idea": plan_longs[i]})
    plan = {"date": date_str, "shorts": sum(1 for s in slots if s["kind"] == "short"),
            "longs": sum(1 for s in slots if s["kind"] == "long"),
            "mix": {k: sum(1 for s in slots if (s.get("idea") or {}).get("pillar") == k)
                    for k in set((s.get("idea") or {}).get("pillar") for s in slots)},
            "best_long_hours_seen": best_long_hours[-3:], "slots": slots}
    _jdump(STATE / f"plan_{date_str}.json", plan)
    return plan


# ───────────────────────────── التقرير اليومي ─────────────────────────────

def daily_report(brain: Brain, plan: dict | None = None, ideas: list | None = None) -> str:
    lines = [f"# 🧠 تقرير Dollars — {date.today().isoformat()}", ""]
    lines.append(f"**خبرة العقل:** {brain.meta.get('samples', 0)} تجربة · "
                 f"معدّل التعلّم {brain.meta['lr']:.2f} · استكشاف {brain.meta['eps']:.2f} · "
                 f"آخر خطأ توقّع {brain.meta.get('last_error')}")
    lines += ["", "## 🏆 أقوى الخصال عندنا دلوقتي", ""]
    for d, o, w, n in brain.winners(10):
        lines.append(f"- **{d}** = `{o}` → وزن {w:.2f} (جرّبناه {n} مرة)")
    if plan:
        lines += ["", "## 🗓️ خطة اليوم", "",
                  f"- شورتس: **{plan['shorts']}** (واحد كل ساعة) · طويلات: **{plan['longs']}**",
                  f"- أحسن ساعات للطويل: {plan.get('best_long_hours_seen')}"]
    if ideas:
        lines += ["", "## 💡 أول 8 أفكار", ""]
        for i in ideas[:8]:
            ch = f" · شخصية {i['character']}" if i.get("character") else ""
            lines.append(f"- [{i['pillar']}/{i['kind']}] `{i['scene']}` · {i['duration']} · "
                         f"خطّاف: {i['hook']} · غلاف: {i['thumb']}{ch} → توقّع {i['predicted']}")
    lines += ["", "## 🔒 الحدود الثابتة",
              "- مفيش سرقة ولا حقوق · مفيش أصوات أشخاص حقيقيين · إفصاح AI إلزامي · "
              "مش محتوى أطفال · التعلّم من أرقامنا بس."]
    return "\n".join(lines)


def run_daily(date_str: str | None = None) -> dict:
    """اللي بيتشغّل تلقائيًا كل يوم في المصنع."""
    brain = Brain.load()
    report_learn = learn(brain)
    ideas = collect_ideas(brain, n=24, date_str=date_str)
    new_chars = spawn_characters(brain, n=2)
    plan = plan_day(brain, date_str, characters=load_characters().get("characters"))
    brain.save()
    ideas_path = _jdump(STATE / "ideas.json", {"generated": datetime.now(timezone.utc).isoformat(),
                                              "ideas": ideas})
    report = daily_report(brain, plan, ideas)
    (STATE / "daily_report.md").write_text(report, encoding="utf-8")
    return {"learn": report_learn, "ideas": len(ideas), "new_characters": [c["name"] for c in new_chars],
            "plan": {"date": plan["date"], "shorts": plan["shorts"], "longs": plan["longs"]},
            "files": [str(ideas_path), str(STATE / "brain.json"), str(STATE / "daily_report.md")]}


if __name__ == "__main__":
    import sys
    out = run_daily(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(out, ensure_ascii=False, indent=2))
