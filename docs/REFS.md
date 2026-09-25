# 🔎 طبقة المراجع والسوق — Dollars Studio

المصنع **بيبحث بنفسه** ويفهم السوق والمرجع البصري — من غير ما ياخد حاجة مسروقة.

## 1) المرجع البصري (Pinterest وأمثاله) — **مشاهدة وتحليل بس**
Pinterest ممنوع يتنزّل منه أي ملف؛ بنقرأ منه المزاج والألوان والتكوين والحركة، وبنحوّلها لإعدادات **عندنا**:

    python engine/refs.py --pinterest "rain on window night"
    python engine/refs.py --recipe "cozy fireplace"
    python engine/refs.py --board "rain on window night" --limit 6   # Openverse (بلا مفتاح)

اللوحات بتروح `docs/refs/<slug>/` ومعاها مصدرها وترخيصها في `state/refs.json` — **وممنوع أي ملف منها يدخل فيديو**.

## 2) من المرجع البصري لإعدادات الفيديو (شغل حقيقي مش ديكور)
`refs.look_recipe("rain on window night")` بترجّع وصفة مونتاج: **مظهر** · **حركة كاميرا** · **مشاهد** ·
**موسيقى** · **ألوان** · **مزاج** — والمصنع بيمرّرها للمخرج:

    rec = refs.recipe_for("satisfying")
    ed.make("satisfying_short", seconds=30, look=rec["look"], moves=rec["moves"],
            scenes=rec["scenes"], music=rec["music"])

- الطويلة: الحركة تيجي من الوصفة، والمظهر من المشهد نفسه (المشهد أعرف بمظهره).
- `refs.recipe_for(pillar)` بتختار أقرب لوحة محفوظة كمان.

## 3) أرقام السوق الحقيقية (يوتيوب)
    python engine/refs.py --trends --apply     # بيسحب أعلى المشاهدات في تخصصاتنا ويفوّد بها العقل

بنسحب النتائج مرتّبة بالمشاهدات من يوتيوب نفسه (`sp=CAMSAhAB`) ونحفظها في `state/trends.json`،
والعقل بياخد منها **دفعة صغيرة (≤0.18)** على أوزان الأنماط — مش انقياد أعمى.

وخطوة `--trends --apply` شغالة أوتوماتيك كل يوم في وركفلو العقل (`studio-daily.yml`).

## APIs المجانية المستخدمة
| الخدمة | مفتاح؟ | بنستخدمها في إيه |
|---|---|---|
| Openverse | لأ | لوحات المرجع البصري |
| Pixabay / Pexels | نعم (اختياري) | مراجع إضافية لو المفاتيح موجودة |
| يوتيوب (بحث الويب) | لأ | أرقام الطلب الحقيقية |
| Cloudflare Workers AI | اختياري | صور AI مجانية (لما نحتاجها) |
