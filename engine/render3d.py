"""
🏔️ محرّك المشاهد ثلاثية الأبعاد — Dollars Studio
=================================================
محرّك 3D كامل مكتوب بـ numpy (بلا GPU · بلا مكتبات · بلا أي حقوق):

  • تضاريس لا نهائية بمنظور حقيقي — بطريقة Voxel-Space: لكل عمود على الشاشة
    بنمشي في المسافة ونسقط ارتفاع الأرض ⇒ تعرّج، إخفاء، مسافة، وضباب حقيقي.
  • إضاءة مسبقة: ظل الشمس + ميل السطح + تدرّج ارتفاع (جبال/عشب/ثلج/رمل).
  • ماء تحليلي: انعكاس السما + فينل + لمعان القمر على الموج + موجات دورية.
  • سما إجرائية: تدرّج + نجوم بتلمع + قمر/شمس + سُحب بتزحف (حلقة مثالية).
  • أجسام: أشجار/صخور/كواكب مرسومة كمثلثات مع اختبار عمق على عمق التضاريس.
  • خريطة عمق جاهزة لكل كادر ⇒ يستخدمها طقم الجودة السينمائية (عمق ميدان + بوكيه).

الحلقة مثالية: الكاميرا · السُحب · الموج · النجوم كلها دوال دورية في الزمن.

الواجهة:
    from engine import render3d
    sc = render3d.make_3d("valley_lake")
    sc.render(0.0)          # صورة float 0..1
    sc.depth(0.0)           # خريطة عمق 0 (قريب) .. 1 (بعيد)
"""
from __future__ import annotations

import math

import numpy as np

from . import visuals as V
from .proc import TAU, fbm, glow, pick_period, splat_fast, tiled_fbm2, smoothstep

NEAR, FAR = 0.35, 900.0
INF = 1e9


# ────────────────────────────── الكاميرا ──────────────────────────────

class Camera:
    def __init__(self, pos, target, fov=48.0, roll=0.0):
        self.pos = np.asarray(pos, np.float32)
        fwd = np.asarray(target, np.float32) - self.pos
        fwd /= max(float(np.linalg.norm(fwd)), 1e-6)
        up0 = np.array([0.0, 1.0, 0.0], np.float32)
        if abs(float(fwd @ up0)) > 0.99:
            up0 = np.array([0.0, 0.0, 1.0], np.float32)
        right = np.cross(fwd, up0); right /= max(float(np.linalg.norm(right)), 1e-6)
        up = np.cross(right, fwd)
        if roll:
            c, s = math.cos(roll), math.sin(roll)
            right, up = right * c - up * s, right * s + up * c
        self.fwd, self.right, self.up = fwd, right.astype(np.float32), up.astype(np.float32)
        self.fov = fov

    def basis_arrays(self, w: int, h: int):
        """أشعة لكل بكسل (شعاع الاتجاه في الفضاء) — تُحسب مرة لكل كادر."""
        fx = (w * 0.5) / math.tan(math.radians(self.fov) * 0.5)
        fy = fx
        cx, cy = w * 0.5 - 0.5, h * 0.5 - 0.5
        xs = (np.arange(w, dtype=np.float32) - cx) / fx
        ys = (cy - np.arange(h, dtype=np.float32)) / fy
        dirs = (self.fwd[None, None, :] + xs[None, :, None] * self.right[None, None, :]
                + ys[:, None, None] * self.up[None, None, :])
        return dirs, xs, ys


# ────────────────────────────── الراسم ──────────────────────────────

def draw_triangles(img, depth, tris_screen, tris_depth, tris_color, cull=True):
    """
    راسم مثلثات بسيط مع اختبار عمق (للأشجار · الصخور · الحلقات).
    tris_screen: (M,3,2) إحداثيات الشاشة · tris_depth: (M,3) المسافة · tris_color: (M,3)
    """
    h, w = img.shape[:2]
    for i in range(len(tris_screen)):
        (x0, y0), (x1, y1), (x2, y2) = tris_screen[i]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 0.7:
            continue
        if cull and area < 0:      # ظهر للمشاهد ⇒ ارميه
            continue
        xa, xb = int(max(0, math.floor(min(x0, x1, x2)))), int(min(w - 1, math.ceil(max(x0, x1, x2))))
        ya, yb = int(max(0, math.floor(min(y0, y1, y2)))), int(min(h - 1, math.ceil(max(y0, y1, y2))))
        if xa > xb or ya > yb:
            continue
        X = np.arange(xa, xb + 1, dtype=np.float32)[None, :]
        Y = np.arange(ya, yb + 1, dtype=np.float32)[:, None]
        inv = 1.0 / area
        l0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) * inv
        l1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) * inv
        l2 = 1.0 - l0 - l1
        inside = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        if not inside.any():
            continue
        d0, d1, d2 = tris_depth[i]
        t = l0 * d0 + l1 * d1 + l2 * d2
        sub_d = depth[ya:yb + 1, xa:xb + 1]
        m = inside & (t < sub_d)
        if not m.any():
            continue
        sub_d[m] = t[m]
        sub = img[ya:yb + 1, xa:xb + 1]
        sub[m] = tris_color[i]
    return img, depth


# ────────────────────────────── القاعدة ──────────────────────────────

class Scene3D(V.Scene):
    """مشهد 3D: بيرجّع صورة + خريطة عمق. الوراثة بتدينا الحبيبات والفينييت والتشطيب."""

    loop_seconds = 40.0
    world_size = 420.0          # مقاس العالم (بيتكرّر — تضاريس لا نهائية)
    grain_amp = 0.008

    def __init__(self, w=1280, h=720, fps=30, seed=7):
        self._depth_cache = None
        self._depth_t = None
        super().__init__(w=w, h=h, fps=fps, seed=seed)

    def depth(self, t: float) -> np.ndarray | None:
        """خريطة عمق (0 قريب · 1 بعيد) مطابقة لآخر render — لعمق الميدان."""
        if self._depth_cache is not None and self._depth_t == float(t):
            return self._depth_cache
        self.render(float(t))
        return self._depth_cache

    def describe(self) -> str:
        return getattr(self, "about", "مشهد ثلاثي الأبعاد متولّد بالكود")

    # ── أدوات مشتركة ──
    def _sky(self, dirs, t, palette, sun_dir, moon_dir, cloud_amt=0.0, star_amt=0.0):
        """سما إجرائية: تدرّج + نجوم + شمس/قمر + سحب بتزحف (كله دوري)."""
        L = self.loop_seconds
        u = t / L
        up = np.clip(dirs[:, :, 1], -1.0, 1.0)
        zen, hor = palette["zenith"], palette["horizon"]
        mixv = np.clip(up, 0.0, 1.0)[:, :, None] ** 0.75
        sky = hor * (1.0 - mixv) + zen * mixv
        below = np.clip(-up, 0.0, 1.0)[:, :, None]
        sky = sky * (1.0 - below) + palette["ground"] * below
        # توهّج الشمس/القمر في السما
        for d, col, pw in ((sun_dir, palette.get("sun", np.array([1.0, 0.85, 0.6], np.float32)), palette.get("sun_pw", 0.5)),
                           (moon_dir, palette.get("moon", np.array([0.8, 0.85, 1.0], np.float32)), palette.get("moon_pw", 0.35))):
            if d is None:
                continue
            cosang = np.clip(dirs @ d, -1.0, 1.0)
            disk = np.power(cosang, 220.0)[:, :, None]
            halo = np.power(cosang, 9.0)[:, :, None]
            sky = sky + disk * (np.asarray(col, np.float32) * (pw * 3.0))[None, None, :]   # قرص
            sky = sky + halo * (np.asarray(col, np.float32) * (pw * 0.55))[None, None, :]  # هالة
        if star_amt > 0:
            stars = self.star_field
            sx = np.mod((dirs[:, :, 0] * 0.5 + 0.5) * stars.shape[1] + u * 0.0, stars.shape[1] - 1).astype(np.int32)
            sy = np.mod((1.0 - (up * 0.5 + 0.5)) * stars.shape[0], stars.shape[0] - 1).astype(np.int32)
            tw = 0.75 + 0.25 * math.sin(TAU * 2 * u)
            star = (stars[sy, sx] * np.clip(up, 0, 1) * (star_amt * tw))[:, :, None]
            sky = sky + star * np.array([1.0, 0.97, 0.92], np.float32)[None, None, :]
        if cloud_amt > 0:
            tex = self.cloud_tex
            shift = int(round(self.cloud_period * 2 * u))     # إزاحة = مضاعف الدورة ⇒ حلقة مثالية
            cl = np.roll(tex, shift, axis=1)
            mask = (np.clip(up, 0.0, 1.0) ** 0.6)[:, :, None]
            light = palette.get("cloud", np.array([0.85, 0.86, 0.92], np.float32))
            sky = sky * (1.0 - cloud_amt * mask * cl[:, :, None]) + \
                  light * (cloud_amt * mask * cl[:, :, None])
        return sky

    def _water(self, dirs, depth, t, level, palette, sky_fn, moon_dir):
        """ماء تحليلي: تقاطع شعاع-مستوى + فينل + انعكاس السما + لمعان القمر + موج دوري."""
        L = self.loop_seconds
        u = t / L
        oy = self.cam.pos[1] - level
        dy = dirs[:, :, 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            dist = np.where(dy < -1e-4, -oy / np.where(dy < -1e-4, dy, -1.0), INF)
        hit = (dist > 0) & (dist < depth) & (dist < FAR)
        dist = np.where(hit, dist, FAR)
        if not hit.any():
            return None, hit, dist
        px = self.cam.pos[0] + dirs[:, :, 0] * dist
        pz = self.cam.pos[2] + dirs[:, :, 2] * dist
        k = TAU / 34.0
        # موجات دورية: كل تردد بعدد صحيح من الدورات في الحلقة
        w1 = 0.5 * np.sin(k * px + 1.7 * u * TAU) + 0.5 * np.sin(k * 0.6 * pz - 2.0 * u * TAU)
        w2 = 0.3 * np.sin(k * 1.7 * (px + pz) + 3.0 * TAU * u)
        n = np.stack([np.full_like(w1, 0.10) * (w2 * 2.0), np.ones_like(w1), np.full_like(w1, -0.16) * (w1 * 2.0)], axis=2)
        n /= np.linalg.norm(n, axis=2, keepdims=True)
        view = -dirs
        fres = np.clip((1.0 - np.clip((view * n).sum(axis=2), 0, 1)) ** 4.0, 0.0, 1.0)
        refl = dirs - 2.0 * (dirs * n).sum(axis=2, keepdims=True) * n
        refl[:, :, 1] = np.abs(refl[:, :, 1])
        sky_col = sky_fn(refl)
        deep = palette["deep"] + palette["shallow"] * np.exp(-dist / 60.0)[:, :, None]
        base = deep * (0.55 + 0.45 * np.clip(0.5 + 0.5 * (w1 * 0.4 + w2 * 0.3), 0, 1))[:, :, None]
        if moon_dir is not None:
            spec = np.clip((refl @ moon_dir), 0.0, 1.0) ** 60.0
            base = base + spec[:, :, None] * palette.get("glitter", np.array([1.0, 0.97, 0.9], np.float32)) * 2.2
        col = base * (1.0 - fres[:, :, None]) + sky_col * fres[:, :, None]
        return col, hit, dist

    def _apply_water(self, img, depth, dirs, t, level, palette, sky_fn, moon_dir):
        out = self._water(dirs, depth, t, level, palette, sky_fn, moon_dir)
        col, hit, dist = out
        if col is None:
            return img, depth
        img[hit] = col[hit]
        depth[hit] = dist[hit]
        return img, depth

    # ── التضاريس (Voxel-Space) ──
    def _sky_color_at(self, rd):
        """لون الجو (تدرّج + شمس/قمر) لاتجاه معيّن — للضباب الجوي. يعمل مع أي عدد من النقاط."""
        p = self.palette
        up = np.clip(rd[:, 1], -1.0, 1.0)
        mixv = np.clip(up, 0.0, 1.0)[:, None] ** 0.75
        col = np.asarray(p["horizon"], np.float32)[None, :] * (1.0 - mixv) + \
              np.asarray(p["zenith"], np.float32)[None, :] * mixv
        below = np.clip(-up, 0.0, 1.0)[:, None]
        col = col * (1.0 - below) + np.asarray(p["ground"], np.float32)[None, :] * below
        for d, key, pwkey, gain in ((getattr(self, "sun_dir", None), "sun", "sun_pw", 0.5),
                                    (getattr(self, "moon_dir", None), "moon", "moon_pw", 0.5)):
            if d is None:
                continue
            ca = np.clip(rd @ np.asarray(d, np.float32), -1.0, 1.0)
            pw = p.get(pwkey, 0.0) * gain
            col = col + (np.power(ca, 9.0) * pw)[:, None] * np.asarray(p[key], np.float32)[None, :]
        return col

    @staticmethod
    def _hash2(x, y):
        """ضجيج عشوائي سريع من الإحداثيات (للتفاصيل الدقيقة على السطح)."""
        s = np.sin(x * 12.9898 + y * 78.233) * 43758.5453
        return s - np.floor(s)

    def _render_terrain(self, img, depth, t):
        """يمشي لكل عمود في المسافة ويرسم التضاريس: إضاءة مسبقة + تفاصيل + ضباب جوي + إخفاء."""
        h, w = self.h, self.w
        u = t / self.loop_seconds
        cam = self.cam
        # حركة الكاميرا: لف دوري + ارتداد رأسي + تقدّم وانحسار
        ang = TAU * u
        rad = self.cam_orbit_r
        cam.pos[0] = self.cam_center[0] + rad * math.cos(ang)
        cam.pos[2] = self.cam_center[2] + rad * math.sin(ang)
        ground = self.sample_height(cam.pos[0], cam.pos[2])
        cam.pos[1] = ground + self.cam_height + self.cam_bob * math.sin(TAU * 2 * u)
        look = np.array([self.cam_center[0] - cam.pos[0], self.look_y - cam.pos[1],
                         self.cam_center[2] - cam.pos[2]], np.float32)
        cam2 = Camera(cam.pos.copy(), cam.pos + look, fov=self.fov)
        dirs, xs, ys = cam2.basis_arrays(w, h)
        self._dirs = dirs
        hrow = dirs[h // 2]
        nrm = np.sqrt(hrow[:, 0] ** 2 + hrow[:, 2] ** 2) + 1e-6
        self._hdir_x = (hrow[:, 0] / nrm).astype(np.float32)
        self._hdir_z = (hrow[:, 2] / nrm).astype(np.float32)

        ybuf = np.full(w, h, np.float32)
        steps = self.ray_steps
        far = self.view_far
        grid = self.hmap
        n = grid.shape[0]
        scale = self.world_size / n
        color_map = self.color_map
        shade_map = self.shade_map
        fy = self.fy_px(h)
        fog_k = float(self.fog_k)
        flat_img = img.reshape(-1, 3)
        flat_depth = depth.reshape(-1)
        # خطوات غير موحّدة: كثيفة قريب (تفاصيل) وواسعة بعيد (مدى)
        kk = np.linspace(0.0, 1.0, steps, dtype=np.float32)
        zs = 1.2 + (far - 1.2) * kk ** 1.45
        for d in zs:
            px_ = cam2.pos[0] + self._hdir_x * d
            pz_ = cam2.pos[2] + self._hdir_z * d
            gxf = np.mod(px_ / scale, n); gyf = np.mod(pz_ / scale, n)
            # ⚠️ الأخطاء العددية بتخلي القيمة تساوي n بالظبط ⇒ نلفّها قبل القص
            gxf = np.where(gxf >= n, 0.0, gxf); gyf = np.where(gyf >= n, 0.0, gyf)
            x0 = gxf.astype(np.int32); y0 = gyf.astype(np.int32)
            fx = np.clip(gxf - x0, 0.0, 1.0); fy_ = np.clip(gyf - y0, 0.0, 1.0)
            x1 = np.mod(x0 + 1, n); y1 = np.mod(y0 + 1, n)
            hgt = (grid[y0, x0] * (1 - fx) * (1 - fy_) + grid[y0, x1] * fx * (1 - fy_)
                   + grid[y1, x0] * (1 - fx) * fy_ + grid[y1, x1] * fx * fy_) * self.height_scale
            sy = np.clip(np.round(fy * (cam2.pos[1] - hgt) / d).astype(np.int32), -1, h + 1)
            cnt = np.maximum(0, ybuf - sy).astype(np.int32)
            tot = int(cnt.sum())
            if tot <= 0:
                continue
            cols = np.repeat(np.arange(w, dtype=np.int32), cnt)
            offsets = (np.arange(tot, dtype=np.int32)
                       - np.repeat(np.cumsum(cnt, dtype=np.int32) - cnt, cnt))
            rows = np.repeat(np.clip(sy, 0, h - 1).astype(np.int32), cnt) + offsets
            ok = (rows >= 0) & (rows < h)
            cols, rows = cols[ok], rows[ok]
            if cols.size == 0:
                continue
            # الإحداثيات العالمية لكل بكسل ملوّن (للتفاصيل والضباب الجوي)
            wx = cam2.pos[0] + self._hdir_x[cols] * d
            wz = cam2.pos[2] + self._hdir_z[cols] * d
            base = color_map[y0, x0][cols]
            shade = shade_map[y0, x0][cols]
            det = self._hash2(wx, wz)
            det2 = self._hash2(wx * 0.22, wz * 0.22)
            tex = 0.86 + 0.22 * det + 0.10 * det2
            col = base * (shade * tex)[:, None]
            # لمعة (ثلج/رمل/ماء مبلل) حسب الخشونة المخزّنة
            if getattr(self, "spec_strength", 0.0) > 0:
                spark = np.clip((det - 0.94) * 16.0, 0.0, 1.0)
                col = col + (spark * self.spec_strength)[:, None] * np.asarray(self.spec_color, np.float32)[None, :]
            # ضباب جوي: نمزج مع لونSky في اتجاه نفس الشعاع
            fogf = np.float32(1.0 - math.exp(-max(float(d) - 0.5, 0.0) * fog_k))
            sky_c = self._sky_color_at(dirs[rows, cols])
            col = col * (1.0 - fogf) + sky_c * fogf
            idx = rows.astype(np.int64) * w + cols.astype(np.int64)
            flat_img[idx] = col
            flat_depth[idx] = d
            ybuf = np.minimum(ybuf, np.clip(sy, 0, None).astype(np.float32))
        return img, depth, cam2, dirs

    # ── خطافات بيستخدمها الراسم ──
    def fy_px(self, h):
        return (h * 0.5) / math.tan(math.radians(self.fov) * 0.5)

    @property
    def cam(self):
        if not hasattr(self, "_cam"):
            self._cam = Camera([0, 5, 0], [0, 2, -1], fov=self.fov)
        return self._cam

    def sample_height(self, wx, wz):
        n = self.hmap.shape[0]
        scale = self.world_size / n
        gx = int(np.mod(wx / scale, n)) % n; gy = int(np.mod(wz / scale, n)) % n
        return float(self.hmap[gy, gx]) * self.height_scale

    def _sample_shade(self, gx, gy):
        n = self.hmap.shape[0]
        return self.shade_map[np.mod(gy.astype(np.int32), n), np.mod(gx.astype(np.int32), n)]

    def _place_objects(self, t, cam2, dirs, img, depth):
        """أشجار/صخور: مثلثات مع اختبار عمق + ثلج على الفروع + ظل تلامس + ضباب جوي."""
        if not self.objects:
            return img, depth
        h, w = self.h, self.w
        fy = self.fy_px(h)
        fog_k = float(self.fog_k)
        snow_col = np.asarray(getattr(self, "snow_color", (0.92, 0.95, 1.0)), np.float32)
        scr, dz, col = [], [], []
        cam_f = cam2.fwd
        for (ox, oz, size, kind, c) in self.objects:
            dx = ox - cam2.pos[0]; dzz = oz - cam2.pos[2]
            along = dx * cam_f[0] + dzz * cam_f[2]
            if along <= 1.5 or along > self.view_far * 0.8:
                continue
            side = dx * cam2.right[0] + dzz * cam2.right[2]
            sx = w * 0.5 + fy * side / along
            if sx < -80 or sx > w + 80:
                continue
            base = self.sample_height(ox, oz)
            sy_ground = h * 0.5 - fy * (cam2.pos[1] - base) / along
            hh = size * fy / along
            ww = hh * 0.5
            fogf = float(1.0 - math.exp(-max(along - 0.5, 0.0) * fog_k))
            rr = int(np.clip(sy_ground, 0, h - 1)); cc = int(np.clip(sx, 0, w - 1))
            sky_here = self._sky_color_at(dirs[rr, cc][None, :])[0]
            body = np.asarray(c, np.float32) * (1.0 - fogf) + sky_here * fogf
            dark = body * 0.55
            if hh < 1.2:
                continue
            if kind == "pine":
                # جذع
                scr.append(((sx - ww * 0.10, sy_ground + hh * 0.10), (sx + ww * 0.10, sy_ground + hh * 0.10),
                            (sx, sy_ground - hh * 0.10)))
                dz.append((along + size * 0.4, along + size * 0.4, along + size * 0.45)); col.append(dark)
                # ثلاث طبقات فروع + ثلج أعلاها
                for i, (frac, spread) in enumerate(((0.95, 1.00), (0.68, 0.78), (0.45, 0.58))):
                    top = sy_ground - hh * frac
                    bot = sy_ground - hh * (frac - 0.34)
                    scr.append(((sx, top), (sx - ww * spread, bot), (sx + ww * spread, bot)))
                    dz.append((along + size * (0.30 - i * 0.05), along + size * 0.3, along + size * 0.3))
                    col.append(body * (0.85 + 0.15 * i))
                    if getattr(self, "snow_trees", 0) > 0:
                        snow_top = top
                        snow_bot = top + (bot - top) * 0.42
                        scr.append(((sx, snow_top), (sx - ww * spread * 0.62, snow_bot), (sx + ww * spread * 0.62, snow_bot)))
                        dz.append((along + size * (0.28 - i * 0.05), along + size * 0.28, along + size * 0.28))
                        col.append(snow_col)
            else:  # صخرة
                for sgn in (-1, 1):
                    scr.append(((sx, sy_ground - hh * 0.75), (sx + sgn * ww * 0.9, sy_ground + hh * 0.08),
                                (sx, sy_ground + hh * 0.14)))
                    dz.append((along, along + size * 0.3, along + size * 0.3)); col.append(body * (1.0 + 0.12 * sgn))
        if scr:
            draw_triangles(img, depth, np.asarray(scr, np.float32), np.asarray(dz, np.float32),
                           np.asarray(col, np.float32), cull=False)
        return img, depth

    # ── الواجهة ──
    def render(self, t):
        raise NotImplementedError

    def _finish(self, t, img, depth, cam2, dirs, sky_sun=(0.7, 0.22)):
        """يخزّن العمق المتطبيع (لعمق الميدان) ويرجّع الصورة."""
        d = np.clip(np.where(depth > INF * 0.5, self.view_far, depth) / self.view_far, 0.0, 1.0)
        self._depth_cache = d.astype(np.float32)
        self._depth_t = float(t)
        self.sun_xy = sky_sun
        return np.clip(img, 0.0, 4.0)

    def prepare(self):
        V.Scene.prepare(self) if hasattr(V.Scene, "prepare") else None
        # اختلافات الكاميرا الافتراضية لكل مشهد
        self.fov = getattr(self, "fov", 48.0)
        self.cam_center = getattr(self, "cam_center", (0.0, 0.0, 0.0))
        self.cam_orbit_r = getattr(self, "cam_orbit_r", 120.0)
        self.cam_height = getattr(self, "cam_height", 26.0)
        self.cam_bob = getattr(self, "cam_bob", 1.2)
        self.look_y = getattr(self, "look_y", 6.0)
        self.ray_steps = getattr(self, "ray_steps", 230)
        self.view_far = getattr(self, "view_far", self.world_size * 0.95)
        self.fog_color = getattr(self, "fog_color", np.array([0.30, 0.34, 0.42], np.float32))
        self.fog_k = getattr(self, "fog_k", 0.016)
        self.height_scale = getattr(self, "height_scale", 46.0)
        self.objects = []
        self.snow_trees = getattr(self, "snow_trees", 0)
        self.spec_strength = getattr(self, "spec_strength", 0.0)
        self.spec_color = getattr(self, "spec_color", (1.0, 1.0, 1.0))
        # نسيج السحب (دوري أfقيًا) + مدى دورته
        self.cloud_period = pick_period(self.w, self.w // 3)
        self.cloud_tex = tiled_fbm2(self.h, self.w, self.seed + 77, max(32, self.h // 2),
                                    self.cloud_period, scales=(4, 8, 16, 32, 64), gain=0.6)
        # ميدان نجوم للسما
        rng = np.random.default_rng(self.seed + 5)
        self.star_field = (rng.random((self.h // 2, self.w // 2), dtype=np.float32) > 0.9985).astype(np.float32) * 2.2
        self._build_world()

    def _build_world(self):
        """المشهد الفرعي بيبني ارتفاعه وألوانه (وفي prepare بنعمل الإضاءة والظل)."""
        raise NotImplementedError

    # ── الإضاءة والظل (مرة واحدة) ──
    def bake_lighting(self, sun_dir=(0.45, 0.62, 0.64), ambient=0.55):
        grid = self.hmap
        n = grid.shape[0]
        gy, gx = np.gradient(grid * self.height_scale, self.world_size / n)
        nx, nz = -gx, -gy
        ny = np.ones_like(grid)
        nl = np.sqrt(nx * nx + ny * ny + nz * nz)
        s = np.asarray(sun_dir, np.float32); s /= np.linalg.norm(s)
        dot = (nx * s[0] + ny * s[1] + nz * s[2]) / nl
        shade = np.clip(ambient + (1.0 - ambient) * np.clip(dot, 0.0, 1.0), 0.34, 1.28)
        self.shade_map = shade.astype(np.float32)

    def build_color_map(self, colors):
        """
        colors: dict بمفاتيح 'low','mid','high','peak' (np.array) — تلوين حسب الارتفاع.
        """
        hgt = self.hmap - self.hmap.min()
        hgt = hgt / max(float(hgt.max()), 1e-6)
        out = np.zeros(self.hmap.shape + (3,), np.float32)
        keys = ["low", "mid", "high", "peak"]
        stops = [0.0, 0.34, 0.62, 0.86]
        for i, k in enumerate(keys):
            lo = stops[i]
            hi = stops[i + 1] if i + 1 < len(stops) else 1.01
            w = np.clip(1.0 - np.abs(hgt - (lo + hi) * 0.5) / max((hi - lo) * 0.5, 1e-3), 0.0, 1.0)
            out += w[:, :, None] * np.asarray(colors[k], np.float32)
        out /= max(float(out.max()), 1e-6)
        self.color_map = out


# ══════════════════════════ 1) وادي وبحيرة ══════════════════════════

class ValleyLake(Scene3D):
    """🏔️ وادي جبلي ببحيرة: جبال + ماء بانعكاس + قمر + ضباب + أشجار صنوبر."""
    name = "valley_lake"
    loop_seconds = 48.0
    about = "وادي جبلي ببحيرة ساكنة، قمر ونجوم، ضباب خفيف على الماء، كاميرا بتلف حوالين البحيرة."

    def _build_world(self):
        n = 256
        hills = tiled_fbm2(n, n, self.seed + 11, n, n, scales=(3, 6, 12, 24, 48), gain=0.5)
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n
        d = np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2)
        rim = smoothstep((d - 0.42) / 0.15)                    # 0 في الحوض · 1 بره
        self.hmap = np.clip(hills * 0.10 * (1 - rim) + rim ** 1.6 * (0.45 + 0.5 * hills), 0, None)
        # تنعيم (تضاريس ناعمة = بلا جروف عمودية؛ عشان المحرّك يبان ناعم مش «مثلثات»)
        for _ in range(3):
            self.hmap = (self.hmap * 4 + np.roll(self.hmap, 1, 0) + np.roll(self.hmap, -1, 0)
                         + np.roll(self.hmap, 1, 1) + np.roll(self.hmap, -1, 1)) / 8.0
        self.hmap = (self.hmap - self.hmap.min()) / float(np.ptp(self.hmap))
        self.build_color_map({
            "low":  (0.10, 0.11, 0.12),      # قاع/شواطئ
            "mid":  (0.13, 0.20, 0.16),      # عشب غامق
            "high": (0.28, 0.29, 0.28),      # صخر
            "peak": (0.72, 0.77, 0.86),      # ثلج على القمم
        })
        self.bake_lighting(sun_dir=(0.30, 0.55, 0.78), ambient=0.46)
        self.height_scale = 30.0
        self.fog_color = np.array([0.10, 0.14, 0.24], np.float32)
        self.fog_k = 0.0088
        self.water_level = 6.5                                # مستوى البحيرة (وحدات عالم)
        self.spec_strength = 0.30
        self.spec_color = (0.85, 0.92, 1.0)
        self.cam_center = (0.0, 0.0, 0.0)
        self.cam_orbit_r = 205.0
        self.cam_height = 42.0
        self.cam_bob = 1.2
        self.look_y = 0.0
        self.ray_steps = 340
        self.fov = 56.0
        self.view_far = self.world_size * 0.72
        rng = np.random.default_rng(self.seed + 21)
        W = self.world_size
        self.objects = []
        for _ in range(40):
            for _try in range(14):
                ox, oz = (rng.random() - 0.5) * W, (rng.random() - 0.5) * W
                hh = self.sample_height(ox, oz)
                if 8.0 < hh < 30.0:
                    self.objects.append((ox, oz, rng.uniform(7, 15), "pine",
                                         np.array([0.05, 0.11, 0.085], np.float32)))
                    break
        self.palette = dict(
            zenith=np.array([0.012, 0.026, 0.070], np.float32),
            horizon=np.array([0.13, 0.17, 0.27], np.float32),
            ground=np.array([0.02, 0.02, 0.03], np.float32),
            sun=np.array([0.5, 0.6, 0.9], np.float32), sun_pw=0.10,
            moon=np.array([0.95, 0.96, 1.0], np.float32), moon_pw=1.0,
            cloud=np.array([0.30, 0.35, 0.50], np.float32),
        )
        self.moon_dir = np.array([0.46, 0.36, 0.81], np.float32); self.moon_dir /= np.linalg.norm(self.moon_dir)
        self.sun_dir = self.moon_dir

    def render(self, t):
        h, w = self.h, self.w
        img = np.zeros((h, w, 3), np.float32)
        depth = np.full((h, w), INF, np.float32)
        img, depth, cam2, dirs = self._render_terrain(img, depth, t)
        # السما ورا كل حاجة غير مرسومة
        sky = self._sky(dirs, t, self.palette, None, self.moon_dir, cloud_amt=0.35, star_amt=1.1)
        sky_mask = depth > INF * 0.5
        img[sky_mask] = sky[sky_mask]
        # قرص القمر (بعد التضاريس عشان يبان فوق)
        cosang = np.clip(dirs @ self.moon_dir, -1, 1)
        disc = (cosang > 0.99985) & sky_mask
        img[disc] = np.array([1.0, 0.99, 0.96], np.float32)
        # الماء
        def sky_fn(refld):
            up = np.clip(refld[:, :, 1], -1.0, 1.0)
            mixv = np.clip(up, 0.0, 1.0)[:, :, None] ** 0.75
            sky = self.palette["horizon"] * (1.0 - mixv) + self.palette["zenith"] * mixv
            cosang = np.clip(refld @ self.moon_dir, -1, 1)
            sky = sky + np.power(cosang, 9.0)[:, :, None] * (self.palette["moon"] * 0.5)[None, None, :]
            return sky
        img, depth = self._apply_water(img, depth, dirs, t, self.water_level, dict(
            deep=np.array([0.012, 0.030, 0.055], np.float32),
            shallow=np.array([0.05, 0.10, 0.14], np.float32),
            glitter=np.array([1.0, 0.98, 0.92], np.float32)), sky_fn, self.moon_dir)
        img, depth = self._place_objects(t, cam2, dirs, img, depth)
        return self._finish(t, img, depth, cam2, dirs, sky_sun=(0.66, 0.30))


# ══════════════════════════ 2) كثبان وقمر ══════════════════════════

class DunesMoon(Scene3D):
    """🌙 كثبان رملية ضخمة تحت قمر كبير: ظلال ناعمة، حرارة لونية، وهدوء تام."""
    name = "dunes_moon"
    loop_seconds = 42.0
    about = "كثبان رملية ناعمة تحت قمر ضخم ونجوم، ظلال طويلة وكاميرا بتزحف ببطء."

    def _build_world(self):
        n = 256
        base = tiled_fbm2(n, n, self.seed + 31, n, n, scales=(2, 4, 8, 16, 64), gain=0.45)
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n
        ridges = 0.5 + 0.5 * np.sin((xx * 7.0 + yy * 2.0) * math.pi + base * 2.2)
        self.hmap = np.clip(base * 0.6 + ridges * 0.55, 0, None)
        self.hmap = (self.hmap - self.hmap.min()) / float(np.ptp(self.hmap))
        self.build_color_map({
            "low":  (0.16, 0.09, 0.05),
            "mid":  (0.40, 0.24, 0.13),
            "high": (0.62, 0.42, 0.24),
            "peak": (0.86, 0.68, 0.44),
        })
        self.bake_lighting(sun_dir=(-0.62, 0.42, 0.66), ambient=0.30)
        self.height_scale = 34.0
        self.fog_color = np.array([0.14, 0.10, 0.14], np.float32)
        self.fog_k = 0.0085
        self.spec_strength = 0.40
        self.spec_color = (1.0, 0.92, 0.72)
        self.cam_center = (0.0, 0.0, 0.0)
        self.cam_orbit_r = 175.0
        self.cam_height = 30.0
        self.look_y = 6.0
        self.ray_steps = 300
        self.fov = 44.0
        self.objects = []
        rng = np.random.default_rng(self.seed + 41)
        W = self.world_size
        for _ in range(22):
            ox, oz = (rng.random() - 0.5) * W, (rng.random() - 0.5) * W
            self.objects.append((ox, oz, rng.uniform(1.5, 3.5), "rock",
                                 np.array([0.22, 0.14, 0.09], np.float32)))
        self.palette = dict(
            zenith=np.array([0.010, 0.014, 0.050], np.float32),
            horizon=np.array([0.13, 0.09, 0.16], np.float32),
            ground=np.array([0.02, 0.01, 0.02], np.float32),
            moon=np.array([1.0, 0.93, 0.80], np.float32), moon_pw=1.25,
            cloud=np.array([0.20, 0.16, 0.26], np.float32),
        )
        self.moon_dir = np.array([-0.42, 0.34, 0.84], np.float32); self.moon_dir /= np.linalg.norm(self.moon_dir)

    def render(self, t):
        h, w = self.h, self.w
        img = np.zeros((h, w, 3), np.float32)
        depth = np.full((h, w), INF, np.float32)
        img, depth, cam2, dirs = self._render_terrain(img, depth, t)
        sky = self._sky(dirs, t, self.palette, None, self.moon_dir, cloud_amt=0.12, star_amt=1.5)
        m = depth > INF * 0.5
        img[m] = sky[m]
        cosang = np.clip(dirs @ self.moon_dir, -1, 1)
        disc = (cosang > 0.99965) & m
        img[disc] = np.array([1.0, 0.97, 0.90], np.float32)
        halo = (np.exp(-((1.0 - cosang) * 180.0)) * 0.25)[:, :, None] * np.array([1.0, 0.92, 0.78], np.float32)
        img += halo * m[:, :, None]
        img, depth = self._place_objects(t, cam2, dirs, img, depth)
        return self._finish(t, img, depth, cam2, dirs, sky_sun=(0.28, 0.26))


# ══════════════════════════ 3) غابة ثلجية ══════════════════════════

class SnowPines(Scene3D):
    """❄️ غابة صنوبر ثلجية وقت الفجر الأزرق + ثلج بيتساقط + شبورة بين الشجر."""
    name = "snow_pines"
    loop_seconds = 44.0
    about = "غابة صنوبر مغطاة بالثلج وقت الفجر الأزرق، ثلج بيتساقط وشبورة خفيفة."

    def _build_world(self):
        n = 192
        self.hmap = tiled_fbm2(n, n, self.seed + 51, n, n, scales=(2, 4, 8, 16, 32), gain=0.5)
        self.hmap = (self.hmap - self.hmap.min()) / float(np.ptp(self.hmap))
        self.build_color_map({
            "low":  (0.10, 0.13, 0.20),
            "mid":  (0.34, 0.40, 0.52),
            "high": (0.70, 0.76, 0.86),
            "peak": (0.95, 0.97, 1.00),
        })
        self.bake_lighting(sun_dir=(0.35, 0.30, 0.88), ambient=0.62)
        self.height_scale = 22.0
        self.fog_color = np.array([0.42, 0.50, 0.62], np.float32)
        self.fog_k = 0.0115
        self.snow_trees = 1
        self.spec_strength = 0.55
        self.spec_color = (1.0, 1.0, 1.0)
        self.cam_center = (0.0, 0.0, 0.0)
        self.cam_orbit_r = 96.0
        self.cam_height = 16.0
        self.look_y = 5.0
        self.ray_steps = 260
        self.fov = 52.0
        rng = np.random.default_rng(self.seed + 61)
        W = self.world_size
        self.objects = []
        for _ in range(120):
            ox, oz = (rng.random() - 0.5) * W * 0.9, (rng.random() - 0.5) * W * 0.9
            self.objects.append((ox, oz, rng.uniform(7, 17), "pine",
                                 np.array([0.045, 0.085, 0.075], np.float32)))
        self.palette = dict(
            zenith=np.array([0.10, 0.16, 0.30], np.float32),
            horizon=np.array([0.55, 0.63, 0.75], np.float32),
            ground=np.array([0.30, 0.34, 0.42], np.float32),
            sun=np.array([1.0, 0.80, 0.62], np.float32), sun_pw=0.30,
            cloud=np.array([0.80, 0.84, 0.92], np.float32),
        )
        self.moon_dir = None
        self.sun_dir = np.array([0.35, 0.28, 0.88], np.float32); self.sun_dir /= np.linalg.norm(self.sun_dir)
        # ثلج متساقط: مجموعات دورية (تهبط وترجع بنفس الترتيب ⇒ حلقة مثالية)
        rng2 = np.random.default_rng(self.seed + 71)
        nn = 700
        self.fl_x = rng2.random(nn, dtype=np.float32) * self.w
        self.fl_y = rng2.random(nn, dtype=np.float32) * self.h
        self.fl_s = (0.6 + rng2.random(nn, dtype=np.float32) * 1.6)
        self.fl_v = rng2.integers(1, 4, nn).astype(np.float32) * (self.h + 20) / self.loop_seconds

    def render(self, t):
        h, w = self.h, self.w
        img = np.zeros((h, w, 3), np.float32)
        depth = np.full((h, w), INF, np.float32)
        img, depth, cam2, dirs = self._render_terrain(img, depth, t)
        sky = self._sky(dirs, t, self.palette, self.sun_dir, None, cloud_amt=0.55, star_amt=0.15)
        m = depth > INF * 0.5
        img[m] = sky[m]
        img, depth = self._place_objects(t, cam2, dirs, img, depth)
        # ثلج قدام الكاميرا (حبيبات)
        yy = np.mod(self.fl_y + self.fl_v * t, h + 20) - 10
        xx = np.mod(self.fl_x + 18.0 * np.sin(TAU * t / self.loop_seconds + self.fl_s), w + 20) - 10
        splat_fast(img, xx, yy, self.fl_s * 0.22, (0.95, 0.97, 1.0))
        return self._finish(t, img, depth, cam2, dirs, sky_sun=(0.55, 0.35))


# ══════════════════════════ 4) كوكب وحلقات ══════════════════════════

class PlanetRings(Scene3D):
    """🪐 كوكب بحلقات في الفضاء: إضاءة جانبية + ضباب الغلاف الجوي + نجوم."""
    name = "planet_rings"
    loop_seconds = 60.0
    about = "كوكب بحلقات في الفضاء مع نجوم وشمس جانبية، وكاميرا بتلف بنعومة حواليه."

    def _build_world(self):
        self.hmap = np.zeros((16, 16), np.float32)
        self.shade_map = np.ones((16, 16), np.float32)
        self.color_map = np.zeros((16, 16, 3), np.float32)
        self.planet_r = 46.0
        self.ring_in, self.ring_out = 62.0, 104.0
        self.cam_center = (0.0, 0.0, 0.0)
        self.cam_orbit_r = 210.0
        self.cam_height = 34.0
        self.look_y = 0.0
        self.view_far = 900.0
        self.objects = []
        self.light_dir = np.array([-0.62, 0.24, 0.75], np.float32); self.light_dir /= np.linalg.norm(self.light_dir)

    def render(self, t):
        h, w = self.h, self.w
        L = self.loop_seconds
        u = t / L
        ang = TAU * u
        cam_pos = np.array([self.cam_orbit_r * math.cos(ang), self.cam_height + 12.0 * math.sin(TAU * 2 * u),
                            self.cam_orbit_r * math.sin(ang)], np.float32)
        cam = Camera(cam_pos, np.array([0, 0, 0], np.float32), fov=44.0)
        dirs, xs, ys = cam.basis_arrays(w, h)
        img = np.zeros((h, w, 3), np.float32)
        # نجوم الخلفية
        rng = np.random.default_rng(self.seed + 91)
        stars = (rng.random((h // 2, w // 2), dtype=np.float32) > 0.9975).astype(np.float32)
        bright = np.repeat(np.repeat(stars * (0.6 + 0.9 * rng.random((h // 2, w // 2), dtype=np.float32)), 2, 0), 2, 1)[:h, :w]
        img += bright[:, :, None] * np.array([1.0, 0.97, 0.92], np.float32)
        img += 0.004
        # الكوكب: كرة تحليلية
        oc = -cam_pos
        b = 2.0 * (dirs @ oc)
        c = float(oc @ oc) - self.planet_r ** 2
        disc = b * b - 4.0 * c
        hit = disc > 0
        sq = np.sqrt(np.maximum(disc, 0.0))
        t0 = (-b - sq) * 0.5
        t0 = np.where(t0 > 0, t0, (-b + sq) * 0.5)
        pos = cam_pos[None, None, :] + dirs * t0[:, :, None]
        nrm = pos / self.planet_r
        lam = np.clip((nrm * self.light_dir).sum(axis=2), 0.0, 1.0)
        # خطوط غازية على السطح (للحيوية): دورية مع z
        band = 0.5 + 0.5 * np.sin(pos[:, :, 1] * 0.28 + 1.4 * np.sin(pos[:, :, 1] * 0.07))
        col_a = np.array([0.72, 0.55, 0.34], np.float32)
        col_b = np.array([0.94, 0.86, 0.68], np.float32)
        surf = col_a * (1 - band)[:, :, None] + col_b * band[:, :, None]
        terminator = np.clip(lam * 1.25, 0.0, 1.0)
        surf = surf * (0.10 + 0.95 * terminator)[:, :, None]
        # هالة الغلاف الجوي (rim light)
        rim = np.clip(1.0 - np.abs((nrm * (-dirs)).sum(axis=2)), 0.0, 1.0) ** 3.0
        surf = surf + (rim * np.clip(lam * 1.6, 0, 1))[:, :, None] * np.array([0.45, 0.60, 1.0], np.float32) * 1.2
        img = np.where(hit[:, :, None], surf, img)
        # الحلقات: مستوى استوائي (y = 0) بحلقات متعددة
        dy = dirs[:, :, 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            tr = np.where(np.abs(dy) > 1e-4, -cam_pos[1] / np.where(np.abs(dy) > 1e-4, dy, 1.0), INF)
        rp = cam_pos[None, None, :] + dirs * tr[:, :, None]
        rr = np.sqrt(rp[:, :, 0] ** 2 + rp[:, :, 2] ** 2)
        in_ring = (tr > 0) & (rr > self.ring_in) & (rr < self.ring_out)
        # شرايط الحلقات: دورية لطيفة
        pattern = 0.45 + 0.55 * np.sin(rr * 0.55) * np.sin(rr * 0.13 + 1.0)
        ring_col = pattern[:, :, None] * np.array([0.82, 0.72, 0.58], np.float32)
        ring_col = ring_col * np.clip(0.6 + 0.4 * np.abs(np.sin(rr * 0.9)), 0.0, 1.0)[:, :, None]
        behind_planet = (tr > t0) & hit
        show_ring = in_ring & ~behind_planet
        img = np.where(show_ring[:, :, None], img * (1 - 0.85) + ring_col * 0.85, img)
        # ظل الكوكب على الحلقات
        shadow = show_ring & ((rp @ (-self.light_dir)) > 0) & (np.abs(rp[:, :, 1]) < 1.5)
        img = np.where(shadow[:, :, None], img * 0.15, img)
        # شمس بعيدة (وهج)
        sun_dir = self.light_dir
        cosang = np.clip(dirs @ sun_dir, -1, 1)
        img += np.power(cosang, 400.0)[:, :, None] * np.array([1.0, 0.96, 0.88], np.float32) * 2.2
        img += np.power(np.clip(cosang, 0, 1), 14.0)[:, :, None] * np.array([0.35, 0.30, 0.22], np.float32)
        depth = np.full((h, w), INF, np.float32)
        depth = np.where(hit, t0, depth)
        depth = np.where(show_ring, np.minimum(depth, tr), depth)
        return self._finish(t, img, depth, cam, dirs, sky_sun=(0.5, 0.5))


SCENES_3D = {
    "valley_lake": ValleyLake,
    "dunes_moon": DunesMoon,
    "snow_pines": SnowPines,
    "planet_rings": PlanetRings,
}

SLEEP_3D = ("valley_lake", "snow_pines", "dunes_moon")
SMILE_3D = ("planet_rings",)


def make_3d(name: str, w: int = 1280, h: int = 720, fps: int = 30, seed: int = 7) -> Scene3D:
    if name not in SCENES_3D:
        raise KeyError(f"مشهد 3D غير معروف: {name} (المتاح: {', '.join(SCENES_3D)})")
    return SCENES_3D[name](w=w, h=h, fps=fps, seed=seed)


# تسجيل المشاهد في سجل المحرّك العام ⇒ تشتغل مع كل الأدوات والمصنع
for _n, _c in SCENES_3D.items():
    V.SCENES[_n] = _c
V.SLEEP_SCENES = tuple(V.SLEEP_SCENES) + SLEEP_3D
V.SMILE_SCENES = tuple(V.SMILE_SCENES) + SMILE_3D
