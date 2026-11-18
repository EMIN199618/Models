# MEDIA OS AI — Yekun hesabat (Mərhələ 5)

**Tarix:** 2026-11-18 · **Ölçmələrin tam cədvəli:** [EVAL_RESULTS.md](EVAL_RESULTS.md) · **Audit:** [AUDIT.md](AUDIT.md) · **Arxitektura:** [ARCHITECTURE.md](ARCHITECTURE.md)

## 1. Mövcud vəziyyət

- Mövcud MEDIA OS AI kodu (Windows kompüterindəki qovluq və ChatGPT linki) bu iş mühitindən əlçatan olmadı. İstifadəçinin qərarı ilə platforma **sıfırdan** quruldu.
- Platforma işləyir: PostgreSQL 16 + pgvector, Redis, FastAPI, worker, dashboard və AI Analyst çat.
- **59 avtomatik test keçir.** Ölçmə skripti (`eval/run_eval.py`) bütün göstəriciləri hesablayır.
- Bütün keyfiyyət göstəriciləri **sintetik** nümunə məlumatı və **oflayn (local) model** üzərindədir. Real DGK məlumatı və real LLM ilə hələ ölçülməyib (bax: bölmə 7).

## 2. İnteqrasiya edilmiş texnologiyalar və onların ölçülə bilən funksiyası

| İstiqamət | Konkret funksiya | Sübut (test / ölçü) |
|---|---|---|
| **1. Redis Caching** | Dashboard, son xəbərlər, semantik axtarış və AI cavabları keşlənir. Rate limit, qısamüddətli yaddaş, TTL, namespace invalidasiyası, `allkeys-lru` + `maxmemory`, hit/miss sayğacları. Redis nasaz olduqda PostgreSQL-ə keçir. | Hit rate **0.975**. p50 **9.9 ms** (Redis ilə) / 14.0 ms (Redis-siz), p95 14.4 / 24.8 ms. Redis söndürüləndə bütün sorğular uğurludur. Canlı HTTP-də dashboard: miss 31.7 ms → hit 4.5 ms. Testlər: `test_cache.py` (7) |
| **2. RAG** | Loader → Cleaning → Metadata → Splitter → Embeddings → pgvector → Reranker → mənbəli cavab. ACL və təsdiq statusu SQL səviyyəsində süzülür. | Recall@4 **1.0**, MRR **0.81**, mənbəyə əsaslanan cavab nisbəti **1.0**, düzgün imtina **1.0**, icazəsiz və ya təsdiqlənməmiş sənəd sızması **0**. Testlər: `test_rag.py` (8) |
| **2. Memory** | Qısamüddətli yaddaş (Redis + PostgreSQL), uzunmüddətli yaddaş (yalnız təsdiqli və icazəli növlər, PII rədd edilir, saxlanma müddəti, yumşaq silinmə, audit), institusional bilik (RAG) ayrıca qatdır. | Davam sualı əvvəlki yeri (Astara) götürür. Başqa istifadəçi söhbəti və yaddaşı görmür (404). Testlər: `test_memory.py` (5) |
| **2. Tool-calling** | 8 alət: sxem yoxlaması, rol icazəsi, timeout, `tool_calls` auditi. Yazma və silmə aləti yoxdur. Hesabat və risk təsdiqi insan qərarı ilə olur. | Alət seçimi **1.0**, alət uğuru **1.0** (12 sual, 14 çağırış), istinadlı cavab **0.92**. Testlər: `test_agent.py` (11 test, 17 hal) |
| **3. GenAI / Prompt / LLM Architecture** | Ayrıca LLM qatı: provayder konfiqurasiya ilə dəyişir, retry, timeout və local fallback var. 8 versiyalı prompt, guardrail-lər, prompt injection neytrallaşdırılır. Token, latency, xəta və xərc ölçülür. | Prompt injection nümunəsi (n39) risk = low. Fallback testi keçir. Token və xərc `llm_calls`-da. Testlər: `test_chains.py` |
| **4. LangChain Building Blocks** | `BaseChatModel`, `SystemMessage` / `HumanMessage` / `AIMessage` / `ToolMessage`, `ChatPromptTemplate` + `MessagesPlaceholder`, `PydanticOutputParser`, Runnable, `BaseLoader`, `RecursiveCharacterTextSplitter`, `Embeddings`, `BaseRetriever`, `StructuredTool` | Bütün zəncirlər bu bloklardan qurulub; ayrıca paralel backend yoxdur |
| **5. LCEL** | 5 zəncir: `RunnableSequence` (`\|`), `RunnableParallel` (kateqoriya ‖ sentiment, statistika ‖ mətn), `RunnablePassthrough.assign`, `with_retry`, `with_fallbacks`, timeout | Testlər: `test_chains.py` (14) |

## 3. Yeni funksiyalar

- **DGK relevance filtri.** Əlaqəsiz xəbər lentə düşmür: başqa ölkələrin gömrük orqanları, "Gömrükçü" futbol klubu, hava proqnozu və s.
- **Məzmun növünün ayrılması.** Rəsmi xəbər, media materialı və ictimai rəy/şikayət ayrıca təsnif olunur və dashboard-da ayrıca göstərilir.
- **Müstəqil sentiment və risk.** Risk R1–R6 meyarları ilə qiymətləndirilir. Qayda yoxlaması "mənfi = yüksək risk" nəticəsini bloklayır və uydurma sübut id-lərini silir.
- **Fakt yoxlaması.** İddia rəsmi mənbə ilə müqayisə olunur: təsdiq / təkzib / təsdiqlənməyib. Fərqli yerdəki hadisə eyni hadisə sayılmır.
- **Dublikat aşkarlanması.** Dəqiq dublikat sha256 ilə, yaxın dublikat simhash ilə tapılır. Təkrar yayılma (R6) riskə daxil edilir.
- **AI Analyst çatı.** Promptdakı 7 nümunə sual işləyir. Hər cavabda mənbə istinadları ([N12], [S3]), vaxt aralığı və təsdiq statusu var.
- **İnsan yoxlaması növbəsi.** Aşağı etibarlılıqlı nəticələr, orta və yüksək risk siqnalları, hesabat dərci buradan keçir. Hesabatı yalnız admin dərc edə bilər.
- **Metriklər paneli.** Keş, API p50/p95, LLM token və xərci, alət uğuru, collector gecikməsi.

## 4. Dəyişdirilmiş və yaradılmış fayllar

Hamısı yenidir və `mediaos-ai/` qovluğundadır:

- `backend/app/`: `config.py`, `db.py`, `models.py`, `text.py`, `worker.py`, habelə bu alt qovluqlar:
  - `cache/`
  - `llm/` (`provider`, `local_model`, `heuristics`, `embeddings`, `schemas`, `prompts/registry`)
  - `chains/` (`base`, `news`, `rag`, `report`)
  - `rag/` (`ingest`, `retriever`)
  - `memory/`, `agent/` (`tools`, `analyst`), `pipeline/`, `collectors/`, `security/`, `observability/`, `api/main.py`
- `backend/tests/`: 6 test faylı
- `backend/eval/`: `run_eval.py`, `datasets/` (inkişaf, hold-out, RAG və agent sualları)
- `backend/data/samples/`: 45 sintetik xəbər, 7 sintetik sənəd
- `backend/scripts/seed.py`, `backend/Dockerfile`, `backend/requirements.txt`, `backend/.env.example`
- `frontend/`: `index.html`, `app.js`, `styles.css`
- `docker-compose.yml`, `README.md`, `docs/`

## 5. Test nəticələri

```
59 passed in ~9s
```

| Fayl | Testlər |
|---|---|
| `test_cache.py` | 7 — hit/miss, TTL, invalidasiya, istifadəçi izolyasiyası, rate limit (+ Redis-siz), Redis nasaz olduqda API, keş siyasəti |
| `test_rag.py` | 8 — retrieval, ACL, təsdiqlənməmiş sənəd, mənbəli cavab, imtina, uydurma istinadın silinməsi, rol üzrə keş |
| `test_memory.py` | 5 — davam sualı, söhbət izolyasiyası, təsdiq / PII / silinmə / audit, saxlanma müddəti, qatların ayrılığı |
| `test_agent.py` | 17 hal — 7 nümunə sual, təkzibin aşkarlanması, icazə, sxem, timeout, audit, yazma aləti olmaması, hesabat və risk təsdiqi, istifadəçi üzrə keş |
| `test_chains.py` | 14 — LCEL, relevance, injection, qayda yoxlaması, retry/fallback, versiyalar, tool-calling mesajları, yer üzrə fakt yoxlaması (reqressiya) |
| `test_api.py` | 9 — auth, rollar, 429, əlaqəsiz xəbərin lentə düşməməsi, məzmun növləri, dublikat, prompt versiyaları, metriklər |

## 6. Performans və keyfiyyət göstəriciləri

Məlumat sintetikdir, model `local` (oflayn) rejimdədir.

| Göstərici | İnkişaf dəsti (45) | **Hold-out (16)** |
|---|---|---|
| DGK relevance P / R / F1 | 1.0 / 1.0 / 1.0 | **1.0 / 0.92 / 0.96** |
| Məzmun növü dəqiqliyi | 1.0 | **1.0** |
| Kateqoriya dəqiqliyi | 0.89 | **0.64** |
| Sentiment macro-F1 | 0.83 | **0.81** |
| Risk dəqiqliyi | 0.97 (1 FP: rəsmi təkzib "high" alıb) | **1.0** |

- İnkişaf dəsti evristikaları yazarkən istifadə olunub, ona görə onun göstəriciləri optimistdir. **Hold-out dəst daha dürüst göstəricidir.**
- RAG: precision@4 0.42, recall@4 1.0, MRR 0.81. Precision aşağı görünür, çünki hər sualın adətən 1–2 düzgün sənədi var, sistem isə 4 nəticə qaytarır.
- Çat latency: p50 58 ms, p95 78 ms. Bu, local modellə ölçülüb; real LLM ilə saniyələrlə ölçüləcək.
- Pipeline sürəti: təxminən 23 xəbər/saniyə (local model ilə).
- LLM xərci local rejimdə 0-dır. Token sayı təxminidir (simvol/4).

## 7. Qalan problemlər

1. **Real LLM ilə ölçülməyib.** API açarı yoxdur. `MEDIAOS_LLM_PROVIDER=anthropic` qoyub `python -m eval.run_eval` işlədilməlidir. Gözlənti: ən çox kateqoriya dəqiqliyi (hazırda 0.64) yaxşılaşacaq.
2. **Real DGK məlumatı yoxdur.** Toplayıcılar hazırdır, lakin bu mühitdən DGK saytına çıxış bloklanıb. Real mənbələrin RSS və ya API ünvanları konfiqurasiya edilməlidir. Real məlumatdan ən azı 200–300 xəbərlik qızıl etiketli dəst hazırlanmalıdır.
3. **Embedding modeli zəifdir.** `hashing` embeddings sinonimləri tutmur. Neyron model (OpenAI `text-embedding-3-small` və ya lokal çoxdilli model) qoşulmalı və ölçmə təkrarlanmalıdır.
4. **Mövcud MEDIA OS AI kodu ilə müqayisə aparılmayıb.** O kod əlçatan olarsa, hansı hissələrin köçürüləcəyi ayrıca auditdə müəyyən edilməlidir. Promptun "işlək komponenti səbəbsiz əvəz etmə" tələbi buna aiddir.
5. **Docker compose işə salınıb yoxlanmayıb**, çünki bu mühitdə Docker daemon yoxdur.
6. **Yaxın-dublikat axtarışı bütün cədvəli skan edir.** Böyük həcmdə LSH (band) indeksi lazımdır.
7. **Rəsmi təkzib xəbəri (n07) "high" risk alır** və insan yoxlamasına düşür. Bu, təhlükəsiz tərəfə səhvdir, amma artıq yük yaradır.
8. **Autentifikasiya sadədir** (statik API token). Production üçün SSO/LDAP və token rotasiyası lazımdır.
9. **Dev tokenləri** (`mos_dev_*`) yalnız lokal sınaq üçündür. Production-da `seed` işlədilməməlidir.

## 8. Növbəti inkişaf mərhələləri

1. Real LLM açarını qoşmaq, `eval`-i real modellə işlətmək və nəticələri local baseline ilə müqayisə etmək.
2. Real DGK və media mənbələrini qoşmaq, 2 həftəlik real məlumatla əməliyyat metriklərini toplamaq: collector gecikməsi, keş, latency.
3. Analitiklərlə real məlumatdan qızıl etiketli dəst hazırlamaq və hər prompt dəyişikliyində reqressiya ölçməsini CI-a əlavə etmək.
4. Neyron embedding və cross-encoder reranker əlavə edib RAG precision-ı artırmaq.
5. İnsan yoxlaması qərarlarını etiketli məlumat kimi toplamaq və threshold-ları kalibrləmək.
6. SSO, audit logların SIEM-ə ötürülməsi, backup və monitorinq (Prometheus/Grafana).
