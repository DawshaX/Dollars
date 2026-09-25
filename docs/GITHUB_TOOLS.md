# 🧰 أدوات من جيت هوب — اللي نستخدمه واللي لا

بحثنا في مستودعات مفتوحة للأدوات اللي تخدم المصنع، وكل واحدة ليها **قرار واضح**. القاعدة:
**مفيش كود منسوخ من حد، ومفيش ترخيص بيمنع الاستخدام التجاري**.

| الأداة | الترخيص | تخدمنا في إيه | قرارنا |
|---|---|---|---|
| [Openverse API](https://api.openverse.org) | CC (بيانات) | لوحات المرجع البصري بلا مفتاح | ✅ مستخدمة فعلاً (`engine/refs.py`) |
| [tubescrape](https://github.com/zvodd/tubescrape) | MIT | بحث InnerTube بلا مفتاح ولا كوتة | 🟡 بديل جاهز لو حجبوا الطريقة الحالية |
| [audio-dsp](https://github.com/irmen/audio-dsp) | MIT | تخليق/فلاتر للصوت | 🟡 مصدر أفكار لتوسيع `engine/sfx.py` (كل حاجة عندنا مكتوبة بنفسنا) |
| [MoviePy](https://github.com/Zulko/moviepy) | MIT | مونتاج بايثون | ⛔ لا — إحنا بننادي ffmpeg مباشرة (أسرع وأخف) |
| [ffmpeg-python](https://github.com/kkroening/ffmpeg-python) | Apache-2.0 | غلاف ffmpeg | ⛔ لا — نفس السبب |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | بيانات يوتيوب | 🟡 احتياطي للميتاداتا (مش للنشر) |
| [scrapetube](https://github.com/dermasmid/scrapetube) | MIT | بحث يوتيوب | 🟡 احتياطي |
| [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) | MIT | نصوص الفيديوهات | 🟡 للأبحاث (تحليل المنافسين) |
| Pixabay / Pexels APIs | CC0 | مراجع إضافية | ✅ مدعومة بمفاتيح (اختياري) |
| Cloudflare Workers AI | خدمة مجانية | صور AI عند الحاجة | ✅ خيار متاح |

## قواعد ثابتة
- مفيش نسخ كود من أي مستودع بلا قراءة ترخيصه أولاً، ومفيش استخدام تجاري لأي حاجة NC/GPL في منتجنا.
- الأصل عندنا: كل مشهد/صوت/ملصق/موسيقى **مولّد بالكود** — الأدوات الخارجية للتعلّم/المرجع/الخدمة بس.
