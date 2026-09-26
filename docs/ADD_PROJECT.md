# 🚀 زيادة سقف النشر اليومي (بلا حد) — دليل المشروع الإضافي

## الحقيقة بالأرقام (مقاسة فعليًا عندنا)

| الحاجة | الرقم |
|---|---|
| حصة أي مشروع جوجل في اليوم | **10,000 وحدة** |
| تكلفة رفعة واحدة (`videos.insert`) | **1,600 وحدة** |
| ⇒ سقف مشروع واحد | **~6 رفعات/يوم** |
| مشروعان (اللي عندنا دلوقتي) | **~12 رفعة/يوم** |
| مشروع لكل رفعة/ساعة (24/يوم) | **~5 مشاريع** |

القيد ده **من جوجل نفسه** (مش من المصنع ومش من جيت هوب). مفيش طريقة تلتف حواليه من API —
الحل الوحيد للنشر بلا حد: **مشاريع جوجل متعددة، كل واحد بحصته**. المصنع بيتنقّل بينها لوحده
(`engine/publish.py` → `pick_project()`)، وماينشرش بمشروع غير لما يتأكد إنه على **قناتنا**
(`tools/verify_projects.py`).

---

## اللي محتاج منك (٢ دقيقة لكل مشروع)

### 1) اعمل مشروع جديد في Google Cloud
- افتح: <https://console.cloud.google.com/projectcreate>
- الاسم: `Dollars Nova 3` مثلًا → **Create**

### 2) شغّل YouTube Data API
- وانت جوه المشروع الجديد: <https://console.cloud.google.com/apis/library/youtube.googleapis.com>
- **Enable**

### 3) شاشة الموافقة (لو أول مرة في المشروع)
- <https://console.cloud.google.com/apis/credentials/consent>
- **External** → اسم التطبيق `Dollars Studio` + إيميلك → Save
- Scopes: `https://www.googleapis.com/auth/youtube.upload` و `https://www.googleapis.com/auth/youtube.readonly`
- **Test users**: ضيف إيميل جوجل اللي بيملك القناة
- **Publish app** (مهم — عشان التوكن مايموتش كل ٧ أيام)

### 4) اعمل OAuth Client
- <https://console.cloud.google.com/apis/credentials> → **Create credentials** → **OAuth client ID**
- Type: **Web application**
- **Authorized redirect URIs** → ضيف بالظبط:
  ```
  https://dawshax.github.io/youtube/callback/
  ```
- **Create** → انسخ `Client ID` و `Client secret`

### 5) ضيف السرّين في المستودع
- في <https://github.com/DawshaX/Dollars/settings/secrets/actions> (وكمان <https://github.com/DawshaX/daousha/settings/secrets/actions>) ضيف:
  ```
  YOUTUBE_CLIENT_ID_3     = <Client ID>
  YOUTUBE_CLIENT_SECRET_3 = <Client secret>
  ```
  (المشروع الجاي يبقى `_4`، وهكذا)

---

## اللي هعمله أنا (تلقائي بمجرد ما السرّين يتحطوا)

1. أشغّل `channel-reconnect` في daousha بوضع `url` و `slot: 3` → يطلع **لينك موافقة**.
2. تدوس على اللينك وتوافق → تنسخ العنوان كامل من شريط العنوان وتبعتهولي.
3. أشغّل نفس الحلقة بوضع `token` → التوكن الدائم يتخزن في `_3` في المستودعين.
4. أشغّل `verify-projects` → يتأكد إن المشروع ده على **قناتنا** بالظبط، ويسجّله كمشروع مؤهّل.
5. المصنع يستخدمه لوحده من اللحظة دي → **السقف زاد ٦ رفعات/يوم** وظهر في `factory.py --quota`.

---

## أرقام بتتحدّث لوحدها

- `python engine/factory.py --quota` → كام رفعة مستخدمة وكام فاضلة لكل مشروع.
- سجل حيّ: <https://github.com/DawshaX/Dollars/issues/1> → كل خطوة المصنع بيعملها لحظة بلحظة.
- تقرير القناة (`channel-report`) → بيطبع عدد المشاريع المؤهّلة وسقف النشر اليومي.

## ملاحظات مهمة (من التجربة الفعلية)

- **اعتماد بمشروع تاني = خطر نشر على قناة غلط.** عشان كده فيه بوابة أمان: أي مشروع مايتستخدمش
  غير بعد `channels.list?mine=true` يرجّع **نفس** مُعرّف قناتنا. (جرّبنا اعتماد XTreNDAW → رجع قناة
  تانية → اترفض تلقائيًا.)
- توكنات قديمة/ميتة بترجع `HTTP 400` في التبديل → البوابة بتتجاهلها وبتقول السبب، مفيش نشر غلط.
- لما كل المشاريع تخلص حصتها: المصنع **مش بيرندر** على الفاضي — بيوقف ويسيب الشغل في الطابور،
  وبيكمّل لوحده أول ما الحصة ترجع (بعد منتصف الليل بتوقيت المحيط الهادئ = **7 صباحًا بتوقيتنا**).
