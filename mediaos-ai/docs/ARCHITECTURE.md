# MƏRHƏLƏ 2 — ARXİTEKTURA PLANI

## Məlumat axını

```
NEWS SOURCES (RSS / JSON / API ingest)
     │  app/collectors/collectors.py
     ▼
VALIDATION + DEDUPLICATION          sha256 (dəqiq) + 64-bit simhash, Hamming ≤ 6 (yaxın dublikat)
     ▼
DGK RELEVANCE FILTER  (Chain 1)     əlaqəsiz → status=irrelevant (lentə düşmür), aşağı etibarlılıq → insan yoxlaması
     ▼
POSTGRESQL  ───────────────►  VECTOR INDEX / RAG   (documents + chunks, pgvector HNSW)
     │       ───────────────►  REDIS CACHE          (namespace versiyası ilə invalidasiya)
     ▼
LANGCHAIN + LCEL
     ├─ Chain 2: Category ‖ Sentiment  (RunnableParallel)
     ├─ Chain 3: Risk (rəsmi sübut + qayda yoxlaması) → yüksək risk insan təsdiqinə
     ├─ Chain 4: RAG Analysis
     └─ Chain 5: Executive Report → pending_approval
     ▼
FASTAPI BACKEND  (app/api/main.py)
     ├─ DASHBOARD                       /api/dashboard/stats, /api/news/*, /api/search
     └─ AI ANALYST CHAT  /api/chat      agent: MEMORY + RAG + TOOL-CALLING
```

## Fayllar

| Fayl | Məsuliyyət |
|---|---|
| `app/config.py` | Bütün parametrlər (`MEDIAOS_*` mühit dəyişənləri) |
| `app/db.py`, `app/models.py` | PostgreSQL, 16 cədvəl, idempotent miqrasiya və rollback |
| `app/cache/redis_cache.py` | Keş, TTL, namespace invalidasiyası, scope izolyasiyası, circuit breaker, rate limit, hit/miss |
| `app/llm/provider.py` | Provayder seçimi, retry, timeout, fallback |
| `app/llm/local_model.py` | Oflayn `BaseChatModel` (`bind_tools` dəstəyi ilə) |
| `app/llm/heuristics.py` | Oflayn analitik məntiq (baseline) |
| `app/llm/prompts/registry.py` | 8 versiyalı prompt + guardrail-lər |
| `app/llm/schemas.py` | Pydantic çıxış sxemləri |
| `app/llm/embeddings.py` | `Embeddings`: hashing / OpenAI |
| `app/observability/metrics.py` | LLM callback: token, latency, xəta, xərc → `llm_calls` |
| `app/chains/*.py` | 5 LCEL zənciri |
| `app/rag/ingest.py` | Document Loaders → Cleaning → Metadata → Splitter → Embeddings → pgvector |
| `app/rag/retriever.py` | `PgVectorRetriever` (ACL + təsdiq filtri), reranker, kontekst qurucusu |
| `app/memory/service.py` | Qısamüddətli / uzunmüddətli yaddaş, saxlanma müddəti, silinmə, audit |
| `app/agent/tools.py` | 8 alət: sxem, icazə, timeout, audit |
| `app/agent/analyst.py` | Agent dövrü, mesaj rolları, mənbə yoxlaması, istifadəçiyə məxsus keş |
| `app/pipeline/process.py` | Xəbər emalı pipeline-ı |
| `app/worker.py` | Planlayıcı |
| `app/security/auth.py` | Bearer token, rollar (viewer < analyst < admin), rate limit |
| `frontend/` | Dashboard + çat + insan yoxlaması + metriklər |
| `eval/run_eval.py` | Qəbul ölçmələri |

## Verilənlər bazası sxemi

`users`, `sources`, `news_items`, `news_analysis`, `documents`, `chunks(embedding vector(384))`, `memory_items`, `conversations`, `chat_messages`, `review_queue`, `reports`, `audit_logs`, `tool_calls`, `llm_calls`, `request_metrics`, `collector_runs`, `schema_version`.

İndekslər: HNSW (`vector_cosine_ops`), GIN (`to_tsvector`), tarix, status, sentiment, risk və simhash üzrə B-tree.

## API endpoint-ləri

| Metod | Yol | Rol | Keş |
|---|---|---|---|
| GET | `/health` | — | — |
| GET | `/api/me` | viewer+ | — |
| GET | `/api/dashboard/stats?days=` | viewer+ | public, 60 s |
| GET | `/api/news/latest` | viewer+ | public, 30 s |
| GET | `/api/news/{id}` | viewer+ | — |
| GET | `/api/search?q=` | viewer+ | rol üzrə, 300 s |
| POST | `/api/chat` | viewer+ (20/dəq) | istifadəçi üzrə, 120 s |
| GET | `/api/conversations/{id}/messages` | sahib | — |
| GET/POST/DELETE | `/api/memory`, `/api/memory/{id}/approve` | sahib | — |
| GET/POST | `/api/review`, `/api/review/{id}/decide` | analyst+ (hesabat dərci: admin) | — |
| GET | `/api/reports`, `/api/reports/{id}` | viewer+ | — |
| POST | `/api/ingest/news`, `/api/ingest/documents` | admin | invalidasiya edir |
| GET | `/api/metrics` | analyst+ | — |
| GET | `/api/prompts` | viewer+ | — |

## Keş strategiyası

| Namespace | Scope | TTL | Invalidasiya |
|---|---|---|---|
| `dashboard` | public | 60 s | yeni xəbər, yoxlama qərarı |
| `latest_news` | public | 30 s | yeni xəbər, yoxlama qərarı |
| `search`, `trends` | `role:<rol>` | 300 / 60 s | yeni xəbər və sənəd |
| `ai_answer` | `user:<id>` | 120 s | yaddaş dəyişəndə həmin istifadəçinin keşi silinir |
| `stm` (söhbət) | `u<id>:<conv>` | 3600 s | TTL |
| `rl` (rate limit) | `u<id>` | 60 s pəncərə | — |

- AI cavabı yalnız söhbətin ilk sualında, yalnız bütün alətlər uğurlu olduqda və hesabat yaradılmadıqda keşlənir.
- Redis nasaz olduqda circuit breaker 5 s ərzində Redis-ə müraciəti dayandırır, bütün oxunuşlar PostgreSQL-dən gedir, rate limit isə proses daxilində davam edir.

## İcra ardıcıllığı (yerinə yetirilib)

1. Sxem, konfiqurasiya və Redis qatı
2. LLM qatı: promptlar, sxemlər, provayder, local model, metriklər
3. RAG ingestion və retriever
4. LCEL zəncirləri 1–5
5. Pipeline və collector-lar
6. Yaddaş
7. Agent və alətlər
8. API, auth, rate limit
9. Testlər (59) və ölçmə (`eval`)
10. Frontend
11. Docker və sənədlər

## Rollback

- **Kod:** bütün dəyişiklik `mediaos-ai/` qovluğundadır; geri qaytarmaq üçün həmin commit revert edilir.
- **Baza:** `app.db.drop_db()` yalnız MediaOS cədvəllərini silir. `prod` mühitində `seed --reset` qadağandır (assert).
- **Konfiqurasiya:** `MEDIAOS_LLM_PROVIDER=local` real LLM-dən dərhal oflayn rejimə qaytarır. Redis söndürülsə belə sistem işləyir.
- **Prompt:** hər prompt versiyalıdır. Versiya hər analizdə `news_analysis.prompt_versions` və `llm_calls` cədvəllərinə yazılır, ona görə hansı nəticənin hansı versiyadan gəldiyi izlənilir.


## Genişlənmə (2026-11-18): Relevance v2, Structure & Management, Risk v2, multimodal

```
Xəbər / post / şərh (+ OCR mətni, + video transkripti)
  → Keyword matching (keywords: L1/L2/L3/EX, AZ/RU/EN/TR, şəkilçi və diakritika toleransı)
  → Entity recognition (org_units, checkpoints, persons + positions: xəbər tarixindəki vəzifə)
  → Semantic relevance (LLM; lüğət siqnalları ipucu kimi ötürülür)
  → Rule merge (xarici gömrük → rədd; LLM ilə lüğət razılaşmırsa → insan yoxlaması)
  → Classification ‖ Sentiment → Risk v2 (none…critical; risk balı ≠ etibarlılıq) → Validation
```

| Yeni komponent | Fayl |
|---|---|
| Lüğət mühərriki, transliterasiya, dil təyini | `app/intel/lexicon.py` |
| Reyestr yükləyicisi (yalnız əlavə edir, heç nəyi silmir) | `app/intel/registry.py`, `data/dgk_registry.json` |
| OCR, transkript axtarışı, SSRF-dən qorunan yükləmə | `app/intel/media.py` |
| Structure və açar söz API-si | `app/api/structure.py` |
| Miqrasiya 003 | `news_analysis`: `relevance_level`, `matched_keywords`, `matched_entities`, `evidence`; `news_items`: `media`, `language`; yeni cədvəllər: `keywords`, `org_units`, `persons`, `positions`, `checkpoints`, `entity_mentions` |

**Yeni endpoint-lər**
- `GET /api/structure`
- `GET /api/persons/{id}`
- `GET /api/checkpoints`
- `GET/POST /api/keywords`
- `PATCH /api/keywords/{id}`
- `GET /api/keywords/{id}/audit`
- `POST /api/keywords/test`
