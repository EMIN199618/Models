# MEDIA OS AI — Yol xəritəsi (DGK 360° Media Intelligence)

Prinsip: hər mərhələ işlək halda bitir. İşləməyən funksiya "işləyir" kimi göstərilmir. Giriş mümkün olmayan mənbə dashboard-da açıq şəkildə göstərilir.

## Mərhələ 1 — Real məlumatla işə salma (növbəti)

- [ ] **Sizin kompüterdə Docker Compose ilə işə salma.** Kod hazırdır, amma bu bulud mühitində Docker yoxdur. İlk işə salmada çıxan xətalar düzəldilməlidir.
- [ ] **EnsembleData tokeni → real TikTok/Instagram toplaması.** Daxil etmə yolu: admin paneli → "Sosial şəbəkələr".
- [ ] **DGK-nın rəsmi Instagram/TikTok hesablarının təsdiqi.** Panelin "hesab axtar" funksiyası ilə tapılıb təsdiqlənməlidir.
- [ ] **customs.gov.az-ın rəsmi xəbər lenti** (RSS/HTML) sizin şəbəkədən. Ardınca `yoxlanmalıdır` statuslu şəxslərin rəsmi səhifə ilə yoxlanması.
- [ ] **Real LLM.** Variantlar: lokal (Ollama və s.) və ya API. Sonra `eval` yenidən işlədilir. Gözlənti: kateqoriya dəqiqliyi yaxşılaşacaq (hazırda hold-out üzrə 0.64).

## Mərhələ 2 — 360° mənbələr

| Platforma | Qanuni yol | Lazım olan |
|---|---|---|
| Telegram ictimai kanallar | Telegram API (MTProto, öz hesabınızla) və ya `t.me/s/<kanal>` ictimai önizləməsi | API ID/hash və ya şəbəkə icazəsi |
| YouTube | YouTube Data API v3: axtarış, şərhlər, mövcud transkriptlər | API açarı (gündəlik kvota 10 000 unit) |
| Facebook ictimai səhifələr | Graph API, Page Public Content Access | Meta app review |
| X | X API (ödənişli plan) | API planı |
| Xəbər saytları | RSS + sitemap + robots.txt-ə uyğun HTML | Mənbə siyahısı |
| Forumlar, bloqlar | RSS/HTML, istifadə şərtlərinə uyğun | Mənbə siyahısı |

Ödənişli xidmətlər yalnız sizin təsdiqinizlə qoşulacaq. Hər mənbə üçün göstəriləcək: son yoxlama, son uğurlu toplama, son aşkarlanan element, interval, xəta və aşkarlama gecikməsi. Polling intervalı 1–5 dəqiqədir, amma platformanın limiti daha sərtdirsə, ona əməl olunur.

## Mərhələ 3 — Multimodal (16 GB RAM + NVIDIA GPU)

- **OCR:** hazırdır (Tesseract). İstəsəniz PaddleOCR (GPU) ilə müqayisə edilə bilər.
- **Speech-to-text:** faster-whisper `small` (GPU, int8 ≈ 1 GB VRAM), CPU fallback `base`.
- **Vision:** kiçik VLM (məs. Qwen2-VL-2B, 4-bit). Yalnız səhnə/obyekt təsviri; üz tanıma yoxdur.
- **Resurs planı:** modellər eyni anda yüklənmir. Tək GPU növbəsi var: OCR → STT → Vision ardıcıl işləyir. Model emaldan sonra boşaldılır. VRAM < 4 GB olduqda CPU fallback istifadə olunur.

## Mərhələ 4 — Dashboard (enterprise səviyyə)

- [ ] Live Media Feed: vizual kartlar (thumbnail, video önizləmə, platforma, relevance, sentiment, risk).
- [ ] Detailed Intelligence View: iddialar, sübutlar, əlaqəli materiallar, analitik qeydi.
- [ ] Risk Radar: trend, hadisə kartları, "yanlış pozitiv" işarəsi, düzəliş tarixçəsi.
- [ ] Social Analytics, Source Monitoring.
- [ ] Reports Center: PDF və Excel ixracı.
- [ ] Şərhlərin mövzu üzrə klasterləşdirilməsi; eyni hadisənin hadisə kartında birləşdirilməsi (embedding + vaxt pəncərəsi).
- [ ] Frontend-in Next.js-ə köçürülməsi. Bunu Windows-dakı layihə ilə birləşdirmə qərarından sonra edirik.

## Mərhələ 5 — Keyfiyyət

- [ ] Real məlumatdan 300+ etiketli nümunə (analitiklərlə).
- [ ] Prompt dəyişikliklərində CI reqressiyası.
- [ ] Risk qaydalarının etiketli məlumatla kalibrləşdirilməsi.
- [ ] Playwright e2e testləri CI-da.

## Bitmiş mərhələlər

1. Əsas platforma: Redis, RAG, Memory, Tool-calling, LLM qatı, LCEL.
2. EnsembleData inteqrasiyası (kod).
3. Açar söz auditi.
4. Relevance v2 və idarə olunan lüğət.
5. DGK Structure & Management.
6. Risk v2.
7. OCR və SSRF qoruması.
