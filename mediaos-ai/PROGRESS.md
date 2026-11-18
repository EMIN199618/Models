# MEDIA OS AI — İrəliləyiş

**Son yeniləmə:** 2026-11-18 · **Testlər:** 102/102 keçir ([TEST_RESULTS.md](TEST_RESULTS.md))

## Vacib qeyd: hansı layihə

Bu repo (`Models/mediaos-ai`) bulud sessiyasında sıfırdan qurulmuş MEDIA OS AI-dir.

- Windows kompüterinizdəki "MediaOS AI — DGK Demo Edition" layihəsi bu mühitdən **görünmür**.
- O layihədə olan Next.js frontend, Celery, Leadership Monitoring modulu və köhnə açar söz bazası burada **yoxdur**.
- Burada onların əvəzinə bu mühitdə qurulub yoxlanılmış komponentlər var. Hər biri aşağıda göstərilib.

## Mərhələ cədvəli

| Mərhələ | Vəziyyət |
|---|---|
| 1. Əsas platforma: FastAPI, PostgreSQL+pgvector, Redis, RAG, yaddaş, agent, LCEL | ✅ İşləyir |
| 2. Instagram + TikTok (EnsembleData) | ✅ Kod hazırdır və real API-yə qoşulur. ⛔ Token verilmədiyi üçün real toplama aparılmayıb |
| 3. Açar söz bazasının auditi ([docs/KEYWORD_AUDIT.md](docs/KEYWORD_AUDIT.md)) | ✅ |
| 4. Relevance v2: idarə olunan lüğət, L1/L2/L3, AZ/RU/EN/TR, semantik əlaqə, sübut | ✅ Auditdəki kritik yanlış pozitiv (P1) düzəldilib |
| 5. DGK Structure & Management | ✅ 31 bölmə, 24 şəxs, 30 vəzifə qeydi (tarixçə ilə), dashboard bölməsi |
| 6. Risk v2: none/low/medium/high/critical, bal ≠ etibarlılıq | ✅ |
| 7. Multimodal | ⚠ OCR işləyir; Vision AI və speech-to-text yoxdur |
| 8. 360° platformalar (Telegram, YouTube, Facebook, X, forumlar) | ⛔ Başlanmayıb (ROADMAP-a bax) |
| 9. Lokal LLM (Ollama) — demo | ✅ Kod, Docker və `start-demo.bat` hazırdır; Ollama API formatında test serveri ilə yoxlanılıb. ⛔ Real model bu mühitdə işə salınmayıb (Ollama reyestri bloklanıb, GPU yoxdur) |

## Bu mərhələdə nə tamamlandı

**Açar söz və relevance v2**
- `keywords` cədvəli: 98 termin, 4 dil, səviyyələr L1/L2/L3 və istisna.
- Admin API: əlavə etmək, redaktə etmək, aktiv/deaktiv etmək, audit tarixçəsi, effektivlik statistikası (tapılıb/qəbul/rədd) və mətn yoxlama aləti.
- Açar sözlər silinmir; mövcud sözlər qorunur.
- Lüğət prosesdə 60 saniyə keşlənir və dəyişiklikdə dərhal yenilənir.

**Uyğunluq qaydaları**
- L3 sözləri (idxal, ixrac, ƏDV, tarif, sərhəd…) tək başına heç vaxt xəbəri qəbul etdirmir.
- Yer adı tək başına DGK demək deyil; eyni cümlədə gömrük konteksti lazımdır.
- Gömrük sözü olmayan, amma "keçid + yük + sənəd yoxlaması" kimi gömrük prosesini təsvir edən mətn **"yoxlanmalıdır"** statusu alır.
- Pasport/viza nəzarəti başqa qurumun (Dövlət Sərhəd Xidmətinin) səlahiyyəti kimi qeyd olunur.
- Azərbaycan dilinin şəkilçiləri və samit əvəzlənməsi (gömrük → gömrüyü), rus dilinin hal şəkilçiləri (Астара → в Астаре) və diakritikasız yazılış ("gomruk") tanınır.

**Relevance zənciri.** Ardıcıllıq belədir: açar söz → varlıq → LLM → qayda ilə birləşdirmə. LLM və lüğət razılaşmadıqda nəticə insan yoxlamasına gedir. Hər xəbər üçün tapılmış sözlər, varlıqlar və sübut saxlanılır.

**Structure & Management**
- Reyestr: `data/dgk_registry.json`. Mənbələr `customs.gov.az`-ın rəsmi səhifələri (axtarış indeksi vasitəsilə) və media xəbərləridir.
- Statuslar: təsdiqlənmiş 10, yoxlanmalıdır 11, keçmiş rəhbər 9.
- Sizin verdiyiniz 4 nəfər mediada təsdiqini tapır, amma rəsmi səhifələri bu mühitdən oxunmadı. Ona görə "yoxlanmalıdır" statusundadırlar: Elmir Ramazanov, Vüqar Əliyev, Fuad Aslanov, Rövşən Namazov.
- Köhnə xəbər şəxsi **həmin tarixdəki** vəzifəsi ilə əlaqələndirir. Məsələn, 2023-cü il xəbərində Elmir Ramazanov "rəis müavini" kimi tanınır.
- Eyniadlı şəxslər qarışdırılmır: ad yalnız DGK konteksti olduqda sayılır.
- Şəxs üzrə reputasiya balı yoxdur.

**Risk v2**
- Adi rəsmi məlumat və uğurlu əməliyyat → "risk yoxdur".
- "Kritik" üçün ağır meyar + geniş yayılma + təsdiq tələb olunur.
- Risk balı və model etibarlılığı ayrı sahələrdir.

**OCR.** Tesseract aze+rus+tur+eng ilə şəkildəki yazı oxunur və analizə "[Şəkildəki mətn (OCR)]" bloku kimi əlavə olunur.

**Video transkript.** Transkriptdə DGK ifadələri vaxt nişanı ilə tapılır. Bu, yalnız transkript platformadan gəldikdə işləyir.

**Təhlükəsiz media yükləmə (SSRF qoruması):** yalnız https, yalnız icazəli hostlar, yönləndirmə yoxdur, şəxsi IP-lər bloklanır, ölçü limiti var.

## Hansı mənbələr real işləyir

| Mənbə | Vəziyyət |
|---|---|
| RSS lentləri | ✅ Kod hazırdır (`MEDIAOS_COLLECTOR_FEEDS`). Lent konfiqurasiya edilməyib |
| JSON/API ingest | ✅ |
| TikTok, Instagram (EnsembleData) | ✅ Kod hazırdır və real API-yə qoşulur. ⛔ Token yoxdur |
| customs.gov.az | ⛔ Bu bulud mühitindən TLS bağlantısı sayt tərəfindən kəsilir. Sizin kompüterinizdən işləməlidir |
| Telegram, YouTube, Facebook, X | ⛔ İnteqrasiya yoxdur |
| Bütün xəbərlər bazada | **SİNTETİK** (nümunə) məlumatdır, "nümunə" kimi işarələnib |

## Hansı AI modulları real işləyir

| Modul | Vəziyyət |
|---|---|
| Relevance, sentiment, risk, RAG, agent | Bu mühitdə oflayn **local** model (evristika) ilə işləyir. Demo üçün **Ollama** (`qwen2.5:7b-instruct`) qoşulub — sizin kompüterdə işləyəcək; keyfiyyəti orada ölçülməlidir |
| Embedding | `hashing` (oflayn). Neyron model qoşulmayıb |
| OCR | Real (Tesseract) |
| Vision AI | Yoxdur |
| Speech-to-text | Yoxdur |

## Nə yarımçıqdır

- Dashboard-un 360° bölmələri (Live Media Feed vizual kartları, Risk Radar, Social Analytics, Reports export) yalnız qismən var. Xəbər lenti hələ cədvəl şəklindədir.
- Şərhlərin mövzu üzrə klasterləşdirilməsi və hadisə kartları hazır deyil.
- Docker Compose yazılıb, amma bu mühitdə Docker daemon yoxdur və işə salınıb yoxlanmayıb.

## Növbəti addım

ROADMAP.md-dəki 1-ci mərhələ: Docker ilə sizin kompüterdə işə salma, EnsembleData tokeni, real LLM.
