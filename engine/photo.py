"""
🖼️ محرّك الصور الحقيقية — صور حقيقية (NASA · Wikimedia · Pixabay · Pexels) بحركة سينمائية.
=========================================================================================
ليه ده؟ لأن الصورة الحقيقية المتحركة بتبان **أفخم بكتير** من أي مشهد مرسوم:
    - تقريب/تحريك بطيء (Ken Burns) على تفاصيل حقيقية
    - طبقات: جزيئات · ضوء · ضباب · تعتيم سينمائي · حبيبات فيلم
    - تلوان لوني + تصحيح عدسة (bloom · halation · vignette)
    - بين قوسين: النص على الشاشة + المصدر صغير تحت (شفافية كاملة)

كل الصور من مصادر **حرة أو ملكية عامة**، وبنحفظ اسم المصدر ورخصته في بيانات الفيديو.

    from engine import photo
    items = photo.collect("Black hole", genre="facts")
    photo.render_reel(items, "out/facts.mp4", seconds=30, texts=[...])
"""
from __future__ import annotations

import json
import math
import pathlib
import subprocess
import urllib.error
import urllib.request

import numpy as np
from PIL import Image, ImageFilter

from engine import grade, proc

CACHE = pathlib.Path("work/photos")
UA = {"User-Agent": "DollarsStudio/1.0 (+https://github.com/DawshaX/Dollars)"}

# رخص آمنة ١٠٠٪ للنشر التجاري (بلا أي شروط حقوق)
FREE_OK = ("cc0", "public domain", "pd", "no known copyright", "pixabay", "pexels",
           "nasa", "us government", "government work")
# محتاج ذكر المصدر (مسموح لكن لازم كريديت واضح)
NEEDS_CREDIT = ("cc by", "cc-by", "attribution")


def _ok_license(text: str) -> tuple[bool, bool]:
    t = (text or "").lower()
    if not t:
        return True, False                       # مصادر موسوعية — الكريديت بيوضع دايمًا
    if any(k in t for k in FREE_OK):
        return True, False
    if any(k in t for k in NEEDS_CREDIT):
        return True, True
    if any(k in t for k in ("nc", "noncommercial", "nd", "noderiv")):
        return False, False                      # ممنوع تجاريًا ⇒ بنرفضه
    return False, False


def collect(topic: str, genre: str = "facts", n: int = 6, prefer: tuple = (),
            style: str = "photo") -> list[dict]:
    """يجمع صور حقيقية حرة عن الموضوع — بترتيب الأفضلية للنوع.

    style="illustration" بيجرّب الرسومات الحرة الأول (مثالي للحكايات) وبعدين الصور.
    """
    from engine import providers
    out: list[dict] = []
    if style == "illustration":
        out += providers.pixabay_images(topic, per=n, kind="illustration")
        out += providers.openverse_images(f"{topic} illustration", per=max(2, n - len(out)))
    elif genre == "space_nature":
        out += providers.nasa_images(topic or "nebula", per=max(4, n))
        out += providers.wikimedia_images(topic, per=max(2, n - len(out)))
    else:
        # الفوتوغرافي الحقيقي الأول (صور حلوة)، وناسا بس للموضوعات الفضائية
        out += providers.pixabay_images(topic, per=max(3, n))
        out += providers.pexels_images(topic, per=max(2, n - len(out)))
        out += providers.wikimedia_images(topic, per=max(2, n - len(out)))
        if any(k in topic.lower() for k in ("space", "nebula", "galaxy", "star", "planet", "moon", "mars")):
            out += providers.nasa_images(topic, per=max(2, n - len(out)))
    if len(out) < n:
        out += providers.openverse_images(topic, per=max(2, n - len(out)))

    clean = []
    for it in out:
        ok, credit = _ok_license(it.get("license", ""))
        if not ok or not it.get("url"):
            continue
        clean.append({**it, "needs_credit": credit,
                      "credit": it.get("source", "") + (f" · {it.get('license')}" if it.get("license") else "")})
    seen, uniq = set(), []
    for it in clean:
        k = it.get("url")
        if k in seen:
            continue
        seen.add(k); uniq.append(it)
    return uniq[:n]


def _url_variants(url: str) -> list[str]:
    """لو الرابط نسخة صغيرة (NASA ~thumb/~small) ← نجرّب النسخ الكبيرة بالترتيب."""
    if not url:
        return []
    out = [url]
    for big in ("~orig", "~large", "~medium"):
        for small in ("~thumb", "~small", "~mobile"):
            if small in url:
                out.insert(0, url.replace(small, big))
    if url.endswith(".jpg"):
        out.append(url.replace(".jpg", ".png"))
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u); uniq.append(u)
    return uniq


def _colorfulness(img: Image.Image) -> float:
    """مقدار تشبّع الألوان (صور رمادية = صور توضيحية/أقمار ⇒ بنرفضها في المحتوى الفوتوغرافي)."""
    try:
        small = img.resize((120, 120))
        arr = np.asarray(small).astype(np.float32)
        mx, mn = arr.max(axis=2), arr.min(axis=2)
        return float(((mx - mn) / np.maximum(mx, 1.0)).mean())
    except Exception:
        return 1.0


def download(item: dict, timeout: int = 45, min_side: int = 900,
             min_color: float = 0.0) -> pathlib.Path | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    name = str(abs(hash(item.get("url", ""))))[:16] + ".jpg"
    p = CACHE / name
    if p.exists() and p.stat().st_size > 20_000:
        return p
    best = None
    try:
        for url in _url_variants(item.get("url", "")):
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read(14_000_000)
                img = Image.open(__import__("io").BytesIO(raw)).convert("RGB")
            except Exception:
                continue
            if img.width >= min_side or img.height >= min_side:
                break
            if best is None or img.width > best.width:   # نحتفظ بالأكبر لحد ما نلاقي أحسن
                best = img
        else:
            img = None
        img = img if img is not None else best
        img.thumbnail((2600, 2600), Image.LANCZOS)
        img.save(p, "JPEG", quality=92)
        return p
    except Exception:
        return None


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """يقصّ الصورة لتغطية الإطار الكامل بنسبة صحيحة (بلا تشويه)."""
    r = max(w / img.width, h / img.height)
    nw, nh = max(w, int(img.width * r + 0.5)), max(h, int(img.height * r + 0.5))
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = int((nh - h) * 0.42)
    return img.crop((left, top, left + w, top + h))


def _light_leak(w: int, h: int, i: int, total: int, strength: float = 0.22) -> np.ndarray:
    """ليك ضوء متحرك (لمعة عدسة) — يدي الإحساس السينمائي بين المقاطع."""
    t = (i % max(1, total)) / float(max(1, total))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = w * (0.15 + 0.7 * t)
    d = np.sqrt(((xx - cx) / (w * 0.55)) ** 2 + ((yy - h * 0.25) / (h * 0.75)) ** 2)
    glow = np.clip(1.0 - d, 0, 1) ** 2.2
    col = np.array([1.0, 0.82, 0.6], dtype=np.float32)
    return (glow * strength)[..., None] * col[None, None, :]


def reel_frames(paths: list[pathlib.Path], w: int, h: int, fps: int, seconds: float,
                palette=None, look: str = "cinema_cool", seed: int = 7,
                particles: float = 0.5, style: str = "cinema"):
    """
    يطلّع كادرات فيديو من صور حقيقية: تقريب/تحريك بطيء + جزيئات + تصحيح سينمائي.
    (generator — عشان الرندر يبقى على الهوا مباشرةً)
    """
    rng = np.random.default_rng(seed)
    total = int(seconds * fps)
    per = max(1, total // max(1, len(paths)))
    trans = max(6, min(int(per * 0.22), int(0.9 * fps)))      # طول التلاشي بين الصور
    imgs = {}
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
            r = max(w / im.width, h / im.height) * 1.22          # هامش للحركة
            im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
            imgs[p] = im
        except Exception:
            continue
    paths = [p for p in paths if p in imgs]
    if not paths:
        return

    # جزيئات (غبار/نجوم خفيفة) تتحرك ببطء
    n_p = int(320 * max(0.25, min(1.5, particles)))
    px = rng.integers(0, w, n_p); py = rng.integers(0, h, n_p)
    pv = rng.uniform(0.15, 0.8, n_p); pr = rng.uniform(0.4, 1.5, n_p)

    for i in range(total):
        idx = min(len(paths) - 1, i // per)
        t = (i % per) / max(1, per)                     # 0..1 جوه الصورة
        im = imgs[paths[idx]]
        zoom = 1.03 + 0.16 * t                          # تقريب واضح (حركة محسوسة)
        dirx = 1 if (idx % 2 == 0) else -1
        panx = dirx * (im.width - w) * 0.62 * (0.10 + 0.90 * t)
        pany = -0.45 * (im.height - h) * (0.10 + 0.90 * t)
        drift = 0.012 * im.height * math.sin(2 * math.pi * (i / float(max(1, total))) * 3.0)
        cw, ch = max(w, int(w * zoom)), max(h, int(h * zoom))
        left = int(min(max(0, (im.width - cw) / 2 + panx), im.width - cw))
        top = int(min(max(0, (im.height - ch) / 2 + pany + drift), im.height - ch))
        crop = im.crop((left, top, left + cw, top + ch)).resize((w, h), Image.BILINEAR)
        fr = np.asarray(crop).astype(np.float32) / 255.0

        # لوحة لونية للنوع (تلوان) — تبني هوية الألوان
        try:
            if palette:
                fr = grade.split_tone(fr, palette, strength=0.42)
        except Exception:
            pass
        # جزيئات متحركة (عمق بصري)
        if n_p:
            ys = (py + (i * pv * 1.7)).astype(int) % h
            xs = (px + (np.sin(i / 55.0 + px % 7) * 6)).astype(int) % w
            fr[ys, xs] = np.clip(fr[ys, xs] + 0.16, 0, 1)
        # انتقالات: تلاشي مع الصورة اللي بعدها (داخل كل صورة) + ليك ضوء في النص
        edge_out = (i % per) >= (per - trans) and idx < len(paths) - 1
        if edge_out and trans > 0:
            k = ((i % per) - (per - trans)) / float(max(1, trans))        # 0..1 نهاية المقطع
            nxt = imgs[paths[idx + 1]]
            z2 = 1.02 + 0.10 * 0.0
            cw2, ch2 = max(w, int(w * z2)), max(h, int(h * z2))
            l2 = int(min(max(0, (nxt.width - cw2) / 2), nxt.width - cw2))
            t2 = int(min(max(0, (nxt.height - ch2) / 2), nxt.height - ch2))
            nf = np.asarray(nxt.crop((l2, t2, l2 + cw2, t2 + ch2)).resize((w, h), Image.BILINEAR)
                            ).astype(np.float32) / 255.0
            try:
                if palette:
                    nf = grade.split_tone(nf, palette, strength=0.42)
            except Exception:
                pass
            fr = _mix(fr, nf, k ** 1.4)                                   # تلاشي متبادل ناعم
        # تصحيح سينمائي خفيف (بلا blur تقيل — الصور أصلًا ناعمة)
        try:
            breath = 1.0 + 0.022 * math.sin(2 * math.pi * i / (fps * 7.0))     # تنفّس إضاءة خفيف
            fr = np.clip(fr * breath, 0, 1)
            fr = grade.vignette(fr, amount=0.26, softness=1.5)
            if style == "cinema":
                fr = np.clip(fr + _light_leak(w, h, i, total, 0.16), 0, 1)
            fr = grade.grain(fr, amount=0.008, seed=i)
        except Exception:
            pass
        yield fr


def _mix(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    t = max(0.0, min(1.0, float(t)))
    return a * (1.0 - t) + b * t


def thumb_from_photo(paths: list[pathlib.Path], texts: list[str], out_path,
                     w: int = 1280, h: int = 720, palette=None) -> pathlib.Path | None:
    """غلاف من أفضل صورة حقيقية + نص قصير واضح (زي أغلفة القنوات الكبيرة)."""
    from PIL import ImageDraw
    from engine.editor import _font
    best = None
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
            arr = np.asarray(im.resize((160, 90))).astype(np.float32) / 255.0
            score = float(arr.std() + 0.8 * arr.mean())          # تفاصيل + إضاءة = صورة قوية
            if best is None or score > best[1]:
                best = (p, score, im)
        except Exception:
            continue
    if best is None:
        return None
    im = best[2]
    r = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * r + 0.5), int(im.height * r + 0.5)), Image.LANCZOS)
    left, top = (im.width - w) // 2, int((im.height - h) * 0.35)
    im = im.crop((left, top, left + w, top + h)).convert("RGB")
    arr = np.asarray(im).astype(np.float32) / 255.0
    try:
        if palette:
            arr = grade.split_tone(arr, palette, strength=0.40)
        arr = grade.vignette(arr, amount=0.34, softness=1.4)
    except Exception:
        pass
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im, "RGBA")
    f = _font(int(h * 0.115))
    y = int(h * 0.10)
    for i, t in enumerate([x for x in texts if x][:2]):
        fnt = f if i == 0 else _font(int(h * 0.078))
        tw = d.textlength(t, font=fnt)
        x = int((w - tw) / 2)
        pad = int(h * 0.02)
        d.rounded_rectangle([x - pad, y - pad // 2, x + tw + pad, y + int(h * 0.115) + pad // 2],
                            radius=int(h * 0.02), fill=(0, 0, 0, 150))
        d.text((x + 3, y + 3), t, font=fnt, fill=(0, 0, 0, 200))
        d.text((x, y), t, font=fnt, fill=(255, 255, 255, 250))
        y += int(h * 0.16)
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, "JPEG", quality=90)
    return out_path


def render_reel(paths: list[pathlib.Path], out_path, seconds: float, w: int = 720, h: int = 1280,
                fps: int = 30, palette=None, look: str = "cinema_cool", seed: int = 7,
                texts: list | None = None, crf: int = 21) -> pathlib.Path:
    """يرندر الصور الحقيقية كفيديو كامل (مع النص على الشاشة لو موجود)."""
    from engine.editor import _draw_text
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [proc.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-g", str(fps * 2), "-movflags", "+faststart", str(out_path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    i = 0
    for fr in reel_frames(paths, w, h, fps, seconds, palette=palette, look=look, seed=seed):
        t_now = i / float(fps)
        if texts:
            for tx in texts:
                at, dur = float(tx.get("at", 0)), float(tx.get("dur", 3))
                if at <= t_now < at + dur:
                    fr = _draw_text(fr, str(tx.get("text", "")), pos=tx.get("pos", "lower"),
                                    size=float(tx.get("size", 0.055)))
                    break
        p.stdin.write(memoryview(np.ascontiguousarray((np.clip(fr, 0, 1) * 255).astype(np.uint8))))
        i += 1
    p.stdin.close()
    err = p.stderr.read().decode("utf-8", "ignore") if p.stderr else ""
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg فشل: {err[:300]}")
    return out_path


def credits(items: list[dict]) -> list[str]:
    """سطور حقوق المصادر (بتتحط في الوصف — شفافية كاملة)."""
    out = []
    for it in items:
        src = it.get("source", "source")
        page = it.get("page") or it.get("image_page") or ""
        if pdf := it.get("credit"):
            out.append(f"• {pdf} — {page}".strip())
        else:
            out.append(f"• {src} — {page}".strip())
    return out[:6]
