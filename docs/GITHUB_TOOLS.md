# 🧰 أدوات جاهزة لقيناها على النت وجيت هوب (بحث حقيقي · فحص ترخيص)
> المعيار: **مجاني · ترخيص بيسمح بالاستخدام التجاري · مفيد فعلًا** — ومفيش كود مسروق: لو استخدمنا حاجة،
> نستخدمها **كمكتبة** بترخيصها المكتوب أو نستلهم الفكرة ونكتبها بأنفسنا.

| الأداة | الترخيص | بتعمل إيه | القرار عندنا |
|---|---|---|---|
| [audio-dsp](https://github.com/Metallicode/python_audio_dsp) | MIT | توليف وأفكتات (subtractive synth · reverb · delay · sequencer) على numpy | ✅ **مرشّح** لتوسيع `engine/music.py`/`sfx.py` (كله numpy — ينفع على رانر 2 نواة) |
| [moviepy](https://pypi.org/project/moviepy/) | MIT | مونتاج بايثون (قص · تركيب · مؤثرات) | ⚠️ مرجع — إحنا بنكلّم ffmpeg مباشرة (أسرع وبلا تبعيات ثقيلة) |
| [ffmpeg-python](https://github.com/kkroening/ffmpeg-python) | Apache-2.0 | تغليف ffmpeg | ⚠️ مرجع — نفس السبب |
| [MovieLite](https://github.com/francozanardi/movielite) | مفتوح (ألفا) | بديل أسرع من MoviePy بـ Numba | ⏳ نراقبه (ألفا) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | ميتاداتا كل الفيديوهات بلا مفتاح | ⏳ احتياطي لو `refs.py --trends` اتمنع من IP |
| [tubescrape](https://github.com/zaidkx37/tubescrape) | MIT | بحث يوتيوب من InnerTube (بلا مفتاح · بلا حصة) | ✅ **مرشّح** كطريقة أوثق لأرقام السوق |
| [scrapetube](https://github.com/dermasmid/scrapetube) | MIT | قوائم بحث | ⏳ احتياطي |
| [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) | MIT | نصوص الفيديوهات | ⏳ لتحليل العناوين/المواضيع لاحقًا |
| [NewPipe Extractor](https://github.com/TeamNewPipe/NewPipeExtractor) | GPL-3.0 | سحب بيانات يوتيوب | ❌ **مرفوض** (GPL-3 ما يصلحش لمشروعنا) |
| [Openverse API](https://api.openverse.org) | CC (بالمصدر) | 800M صورة/صوت مفتوحة | ✅ **مستخدم فعلًا** في `engine/refs.py --board` |
| [Pixabay API](https://pixabay.com/api/docs/) · [Pexels](https://www.pexels.com/api/) | CC0 | صور/فيديو مجاني | ✅ مدعوم في `refs.py` (لما مفتاحك يتحط) |
| [public-apis](https://github.com/tools-collection/apis-collection) | قائمة | كتالوج APIs مجانية | 📚 مرجع دايم للتوسيع |

## مفاتيح الاستخدام عندنا
1. **كودنا أولًا** — أداة خارجية بس لما تكون أحسن فعلًا وخفيفة.
2. ما تدخلش أي مكتبة في السير إلا لو: ترخيص MIT/Apache/CC0/Unlicense + بتشتغل على 2 نواة و2 جيجا رام.
3. أي أصل بصري/صوتي يدخل فيديو = **لازم CC0/ترخيص تجاري + تسجيل المصدر** في `content/library.json`.
