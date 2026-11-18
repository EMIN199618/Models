# DGK açar söz bazası — READ-ONLY audit

**Tarix:** 2026-11-18 · **Rejim:** yalnız oxuma. Kod, baza və konfiqurasiya dəyişdirilməyib. Yoxlamalar evristik funksiyalarla aparılıb, LLM zəncirləri çağırılmayıb ki, bazaya metrik yazılmasın.

## 1. Əhatə və məhdudiyyət

- Audit bu platformanın faktiki vəziyyətini əks etdirir: `mediaos-ai/` kodu, `mediaos` bazası (45 sintetik xəbər) və EnsembleData konfiqurasiyası.
- Promptda xatırlanan **"əvvəlki açar söz bazamız"** (Samur, Şirvanlı, Mazımqara, Sınıq Körpü, Ağbənd və s. olan baza) bu mühitdə yoxdur. Çox güman ki, Windows kompüterinizdəki köhnə MEDIA OS AI layihəsindədir. Ona görə mövcud sözləri o bazayla müqayisə etmək mümkün olmadı.
- Bazadakı xəbərlər sintetikdir. "Hansı açar söz hansı xəbəri topladı" bölməsi real məlumatı deyil, mexanizmin necə işlədiyini göstərir.

## 2. Mövcud açar söz inventarı

Açar sözlər **kodda sabit yazılıb** (`backend/app/llm/heuristics.py`). Bazada açar söz cədvəli yoxdur; idarəetmə, aktiv/deaktiv etmə, statistika və audit tarixçəsi də yoxdur.

| Qrup | Say | Məzmun |
|---|---|---|
| Güclü şablonlar (`STRONG_DGK`) | 12 | 8 azərbaycanca: `dövlət gömrük komitə`, `dgk`, `gömrük komitəsi`, `azərbaycan gömrük`, `gömrük (post\|idarə\|keçid\|orqan\|əməkdaş\|xidmət\|rüsum\|bəyannamə\|ərazi\|nəzarət\|məntəqə\|terminal\|yoxlama\|rəsmiləşdir)`, `e-gömrük`, `sərhəd-keçid`, `gömrükçü`; 4 rusca: `таможенн* комитет`, `гтк`, `таможн* азербайджан`, `азербайджанск* таможн` |
| Orta şablonlar (`MEDIUM_DGK`) | 9 | `gömrü[kyğ]`, `qaçaqmal`, `bəyannamə`, `rüsum`, `aksiz`, `tranzit yük`, `таможн`, `контрабанд`, `растаможк` |
| Yer kataloqu (`AZ_LOCATIONS`) | 17 açar → 16 ad | Astara, Biləsuvar, Qırmızı Körpü, Sədərək, Yalama, Balakən, Ələt, Culfa, Horadiz, Heydər Əliyev Hava Limanı, "hava limanı", Bakı Limanı ("bakı limanı", "dəniz limanı"), Laçın, Zəngilan, Naxçıvan, Gəncə |
| Xarici gömrük istisnası | 12 ölkə | Gürcüstan, Rusiya, Türkiyə, İran, Qazaxıstan, Özbəkistan, Avropa, ABŞ, Çin, Ukrayna, Almaniya, Fransa |
| Mövzu istisnası (`NOISE`) | 5 | `gömrük ittifaqı`, `futbol`, `hava proqnozu`, `konsert`, `serial` |
| Yazılış variantları | — | ASCII çevrilməsi (ə→e, ö→o, ü→u, ğ→g, ı→i, ş→s, ç→c): "gomruk" tanınır, türkcə "gümrük" tanınmır |
| EnsembleData axtarışı | 6 söz + 4 heşteq | Sözlər: Dövlət Gömrük Komitəsi, DGK gömrük, gömrük, gomruk, Astara gömrük, Qırmızı körpü gömrük. Heşteqlər: #gömrük, #gomruk, #dgk, #azerbaijancustoms |
| Rəhbərlik / vəzifəli şəxslər | **0** | Yoxdur |
| İngilis dili | **0** | Yoxdur |

Qərar qaydası: bal = 0.45 × güclü + 0.18 × orta. Yer adı + orta termin varsa, bala +0.45 əlavə olunur. Xarici ölkə: −0.6. Mövzu istisnası: −0.4. Bal ≥ 0.5 olarsa xəbər qəbul edilir. Etibarlılıq < 0.6 olarsa insan yoxlamasına göndərilir.

## 3. Hansı açar söz hansı xəbəri tutdu

Sintetik dəstdə 45 xəbər var. Cədvəldə hər termin üçün göstərilir: neçə xəbərdə tapılıb, onlardan neçəsi qəbul edilib, neçəsi qızıl etiketə görə əslində DGK-ya aiddir və neçəsi aid deyil.

| Termin | Tapılıb | Qəbul edilib | Əslində aid | Əslində aid deyil |
|---|---|---|---|---|
| `gömrü[kyğ]` | 42 | 37 | 37 | 5 |
| `gömrük (post\|idarə\|…)` | 30 | 29 | 29 | **1** (Rusiya Federal Gömrük *Xidməti*) |
| `gömrük komitəsi` | 13 | 13 | 13 | 0 |
| `dövlət gömrük komitə` | 12 | 12 | 12 | 0 |
| `dgk` | 4 | 4 | 4 | 0 |
| `e-gömrük` | 4 | 4 | 4 | 0 |
| `tranzit yük` | 4 | 4 | 4 | 0 |
| `gömrükçü` | 1 | 0 | 0 | **1** ("Gömrükçü" futbol klubu) |
| Yer: Astara | 5 | 5 | 5 | 0 |

Səkkiz əlaqəsiz xəbərin hamısı rədd edilib. Amma ikisi **güclü şablona uyğun gəlib** və yalnız istisna qaydası sayəsində rədd olunub: "Rusiya Federal Gömrük Xidməti" (xarici ölkə qaydası) və "Gömrükçü" futbol klubu (`futbol` istisnası). İstisna siyahısında olmayan oxşar hal (məsələn "Gömrükçü" voleybol komandası) qəbul ediləcək.

## 4. Test halları

Promptun 11-ci bölməsindəki hallar və əlavə yoxlamalar:

| # | Hal | Gözlənilən | Nəticə | |
|---|---|---|---|---|
| 1 | DGK-nın rəsmi xəbəri | qəbul | qəbul (1.0) | ✓ |
| 2 | "Astara rayonunda məktəb təmir edildi" | rədd | rədd (0.0) | ✓ |
| 3 | "Astara gömrük postunda gecikmə" (DGK sözü yoxdur) | qəbul | qəbul (1.0) | ✓ |
| 3b | Samur gömrük postu (kataloqda yoxdur) | qəbul | qəbul (0.63), "gömrük postu" sayəsində | ✓ |
| 3c | "Ağbənd gömrük-sərhəd infrastrukturu" | qəbul | **rədd (0.18)** | ✗ |
| 4 | Qazaxıstan gömrüyü | rədd | rədd | ✓ |
| 4b | Türkcə "Kapıkule gümrük kapısı" | rədd | rədd | ✓ |
| 5 | "DGK sədri müşavirə keçirib" | qəbul | qəbul | ✓ |
| 5b | "Komitə sədri Biləsuvar postunda qəbul keçirib" (DGK adı yoxdur) | qəbul | **rədd (0.0)** | ✗ |
| 6 | "İdxal 12 faiz artıb" | rədd | rədd | ✓ |
| 6b | "ƏDV və tarif dəyişiklikləri" | rədd | rədd | ✓ |
| 7 | Rusca: "Государственный таможенный комитет Азербайджана…" | qəbul | qəbul (0.63) | ✓ |
| 7b | Rusca: "На таможне в Астаре очередь" | qəbul | **rədd (0.18)** | ✗ |
| 8 | Eyni hadisə müxtəlif portallarda | birləşdirilir | demək olar eyni mətn birləşir (simhash, Hamming ≤ 6); fərqli sözlərlə yazılmış nüsxə yoxlanmayıb | ⚠ |
| 9 | Mənfi ictimai rəy fakt kimi təsdiqlənmir | təsdiqlənmir | `claim_verified=false`, insan yoxlamasına gedir | ✓ |
| 10 | Uğurlu əməliyyat avtomatik mənfi sayılmır | mənfi deyil | sentiment: positive, risk: low | ✓ |
| — | EN: "State Customs Committee of Azerbaijan" | qəbul | **rədd (0.0)** | ✗ |
| — | EN: "SCC Azerbaijan" | qəbul | **rədd (0.0)** | ✗ |
| — | ASCII: "Dovlet Gomruk Komitesi" | qəbul | qəbul | ✓ |
| — | Domen: "e.customs.gov.az" | qəbul | **rədd (0.18)** | ✗ |
| — | "Smart Customs" | qəbul | **rədd** | ✗ |
| — | "Sınıq Körpü məntəqəsində elektron növbə" | qəbul | **rədd** | ✗ |

**Yekun:** promptun 10 əsas halından 9-u keçir, 8-ci qismən keçir. Əlavə hallardan 8-i uğursuzdur.

## 5. Aşkar edilmiş problemlər (ciddilik sırası ilə)

### P1 — KRİTİK: zəif termin + yer adı xəbəri avtomatik qəbul edir

Aşağıdakı nümunələrin hamısı DGK-ya aid deyil, amma bal 0.63 alıb **qəbul edilir**:

- "Bakı limanında tranzit yük dövriyyəsi 15 faiz artıb"
- "Astara rayon polisi narkotik qaçaqmalçısını saxlayıb" (polis əməliyyatıdır, gömrük deyil)
- "Naxçıvanda aksiz markası olmayan siqaret satan mağaza cərimələnib" (vergi orqanının işidir)
- "Gəncədə bələdiyyə rüsumları artırılıb"

**Səbəb:** yer adı ilə istənilən "orta" termin birləşəndə +0.45 əlavə olunur. Bu qaydanı mən əvvəlki mərhələdə (sosial şəbəkə inteqrasiyası zamanı) gücləndirmişəm. Məqsəd "Astara gömrüyü" kimi yazılışları tutmaq idi, amma "tranzit yük", "aksiz", "rüsum", "qaçaqmal" kimi zəif terminləri ayırmamışam. Bu, promptun LEVEL 3 qaydasını birbaşa pozur. Sintetik dəstin ölçmələri bunu göstərmədi, çünki dəstdə belə hal yox idi.

### P2 — YÜKSƏK: bəzi güclü şablonlar qeyri-müəyyəndir

- `gömrük xidmət` xarici orqanlara da uyğun gəlir ("Federal Gömrük Xidməti").
- `gömrükçü` idman klublarına uyğun gəlir.
- Hər iki halda nəticə istisna siyahılarına bağlıdır; bu siyahılar natamamdır.

### P3 — YÜKSƏK: məntəqə kataloqu natamamdır və idarə olunmur

- **Yoxdur:** Samur, Şirvanlı, Mazımqara, Sınıq Körpü, Ağbənd. "Cənub-Astara" yalnız "Astara" alt-sətri ilə tutulur.
- **Məntəqə olmayan ümumi yer adları var:** Naxçıvan, Gəncə, Laçın, Zəngilan, "hava limanı". Bunlar uyğunluq dairəsini lazımsız genişləndirir (P1-i gücləndirir).
- Rus və ingilis ad formaları yoxdur ("Астара" tanınmır).
- Struktur, yerləşmə, aktivlik vəziyyəti və son yoxlanma tarixi saxlanılmır.

### P4 — YÜKSƏK: rəhbərlik və vəzifəli şəxslər kataloqu ümumiyyətlə yoxdur

- DGK adı çəkilmədən rəhbərlik haqqında yazılan xəbər tapılmır (hal 5b).
- Bu siyahını mən öz biliyimdən doldurmayacağam: promptun tələbinə görə yalnız təsdiqlənmiş mənbədən (DGK-nın rəsmi saytı və ya sizin köhnə bazanız) götürülməlidir. Vəzifənin başlama və bitmə tarixi də saxlanılmalıdır ki, köhnə və yeni vəzifə sahibləri qarışmasın.

### P5 — ORTA: çoxdillilik natamamdır

- İngilis dili: heç bir termin yoxdur.
- Rus dili: yalnız qurum adı tanınır; "таможня" + yer adı tanınmır.
- Türk dili: yalnız istisna kimi işləyir (bu düzgündür).
- Rəsmi identifikatorlar yoxdur: `customs.gov.az`, `e.customs.gov.az`, "Smart Customs", "e-növbə".
- Orfoqrafik səhvlər üçün qeyri-dəqiq uyğunluq (fuzzy matching) yoxdur.

### P6 — ORTA: açar sözlər kodda sabitdir və idarə olunmur

- Admin paneli, aktiv/deaktiv etmə, kateqoriya, alternativ yazılışlar, şəxs və məntəqə ilə əlaqələndirmə yoxdur.
- Effektivlik statistikası, yanlış pozitivlərin izlənməsi və audit tarixçəsi də yoxdur.
- Dəyişiklik yalnız kod deploy-u ilə mümkündür.

### P7 — ORTA: relevance çıxışı tələb olunan formatda deyil

- `matched_keywords`, `matched_entities`, `evidence` sahələri və `DIRECT`/… səviyyəsi yoxdur.
- Mövcud `accept/review/reject` qərarları `PUBLISH/REVIEW/REJECT`-ə uyğundur.
- Termin başlıqda, mətndə və ya metadata-da tapılmasından asılı olmayaraq eyni çəki alır.

### P8 — ORTA: taksonomiyalar promptdan dardır

| Sahə | Mövcud | Tələb olunan | Çatışmayan |
|---|---|---|---|
| Məzmun növü | 3 | 5 | COMPLAINT, UNVERIFIED_CLAIM (indi `public_opinion` daxilindədir) |
| Sentiment | 3 | 5 | MIXED, UNCERTAIN |
| Risk | 3 | 5 | NONE, CRITICAL |

### P9 — AŞAĞI

- Fərqli sözlərlə yazılmış nüsxələr birləşdirilmir (yalnız demək olar eyni mətn birləşir). Hadisə səviyyəsində klasterləşdirmə lazımdır.
- MCP server yoxdur. Agentin alətləri var, amma açar söz, məntəqə və rəhbərlik alətləri yoxdur.
- Rəsmi Instagram postunun altındakı **istənilən** şərh DGK-ya aid sayılır, mövzudan kənar şərhlər də daxil olmaqla.

## 6. Kod və baza strukturu (əlaqəli hissələr)

| Yer | Rolu |
|---|---|
| `app/llm/heuristics.py` → `relevance()` | Bütün açar söz məntiqi (oflayn model) |
| `app/llm/prompts/registry.py` → `dgk_relevance@1.2.0` | Real LLM üçün relevance promptu. Açar söz siyahısı ötürülmür; model yalnız ümumi təlimatla qərar verir |
| `app/chains/news.py` → `relevance_chain` | Validation → prompt → LLM → qərar |
| `app/pipeline/process.py` | Dedup (sha256 + simhash) → relevance → analiz |
| `app/collectors/ensembledata.py` + `settings` cədvəli | Sosial şəbəkə axtarış sözləri (bazada dəyişdirilə bilir) |
| `news_analysis` cədvəli | Yalnız `relevance_score` və `relevance_reason` (sərbəst mətn) saxlanılır; tapılmış sözlər strukturlu saxlanılmır |
| Açar söz / məntəqə / şəxs cədvəlləri | **Yoxdur** |

## 7. Nəticə və növbəti addım

Mövcud baza əsas hallarda işləyir: rəsmi xəbər, əlaqəsiz Astara xəbəri, xarici gömrük, ümumi iqtisadi xəbər, rus dilində qurum adı, ASCII yazılış. Amma onu promptun tələb etdiyi "idarə olunan, üç səviyyəli, sübut göstərən" sistem saymaq olmaz. Ən təcili məsələ **P1**-dir: o, DGK-ya aid olmayan xəbərlərin lentə düşməsinə birbaşa yol açır.

**Mərhələ 2 (texniki plan) üçün sizdən lazımdır:**

1. Köhnə MEDIA OS AI layihəsindəki açar söz bazası. Faylı, ixracı və ya siyahının mətnini bura yapışdıra bilərsiniz. Mövcud sözlər silinmədən onunla müqayisə ediləcək.
2. DGK rəhbərliyi və struktur rəhbərlərinin təsdiqlənmiş siyahısı, və ya bu siyahını DGK-nın rəsmi saytından götürməyə icazə. Bu mühitdən `customs.gov.az`-a çıxış hazırda bağlıdır.
3. P1 üçün təcili düzəliş icazəsi: zəif terminlər + yer adı artıq avtomatik qəbul etməsin, insan yoxlamasına getsin. Bu, kiçik və geri qaytarıla bilən dəyişiklikdir və testlə yoxlanılacaq.
