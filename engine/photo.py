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
    if genre in ("space_nature", "facts") or "space" in (genre or ""):
        out += providers.nasa_images(topic or "nebula", per=max(3, n))
    if genre in ("facts", "space_nature"):
        out += providers.wikimedia_images(topic, per=max(3, n))
    if len(out) < n:
        out += providers.pixabay_images(topic, per=max(2, n - len(out)))
    if len(out) < n:
        out += providers.pexels_images(topic, per=max(2, n - len(out)))
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


def download(item: dict, timeout: int = 45) -> pathlib.Path | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    name = str(abs(hash(item.get("url", ""))))[:16] + ".jpg"
    p = CACHE / name
    if p.exists() and p.stat().st_size > 20_000:
        return p
    try:
        req = urllib.request.Request(item["url"], headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(12_000_000)
        img = Image.open(__import__("io").BytesIO(raw)).convert("RGB")
        if img.width < 900 or img.height < 600:          # صور صغيرة = جودة ضعيفة على الشاشة
            return None
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


def reel_frames(paths: list[pathlib.Path], w: int, h: int, fps: int, seconds: float,
                palette=None, look: str = "cinema_cool", seed: int = 7,
                particles: float = 0.5):
    """
    يطلّع كادرات فيديو من صور حقيقية: تقريب/تحريك بطيء + جزيئات + تصحيح سينمائي.
    (generator — عشان الرندر يبقى على الهوا مباشرةً)
    """
    rng = np.random.default_rng(seed)
    total = int(seconds * fps)
    per = max(1, total // max(1, len(paths)))
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
    n_p = int(240 * max(0.0, min(1.5, particles)))
    px = rng.integers(0, w, n_p); py = rng.integers(0, h, n_p)
    pv = rng.uniform(0.15, 0.8, n_p); pr = rng.uniform(0.4, 1.5, n_p)

    for i in range(total):
        idx = min(len(paths) - 1, i // per)
        t = (i % per) / max(1, per)                     # 0..1 جوه الصورة
        im = imgs[paths[idx]]
        zoom = 1.02 + 0.10 * t                          # تقريب بطيء
        dirx = 1 if (idx % 2 == 0) else -1
        panx = dirx * (im.width - w) * 0.5 * (0.15 + 0.85 * t)
        pany = -0.35 * (im.height - h) * (0.15 + 0.85 * t)
        cw, ch = max(w, int(w * zoom)), max(h, int(h * zoom))
        left = int(min(max(0, (im.width - cw) / 2 + panx), im.width - cw))
        top = int(min(max(0, (im.height - ch) / 2 + pany), im.height - ch))
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
        # تصحيح سينمائي خفيف (بلا blur تقيل — الصور أصلًا ناعمة)
        try:
            fr = grade.vignette(fr, amount=0.26, softness=1.5)
            fr = grade.grain(fr, amount=0.008, seed=i)
        except Exception:
            pass
        yield fr


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
