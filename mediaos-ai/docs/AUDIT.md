# MƏRHƏLƏ 1 — READ-ONLY AUDİT

**Tarix:** 2026-11-18

## 1. Mövcud MEDIA OS AI layihəsinə giriş

Audit mövcud kodu oxumaqla başlamalı idi. Lakin mövcud kod bu iş mühitindən əlçatan deyildi:

| Yer | Yoxlama nəticəsi |
|---|---|
| `C:\Users\MN\Documents\Codex\2026-11-03\master-execution-prompt-mediaos-ai-dgk` | İstifadəçinin Windows kompüterindədir, bulud sessiyasından əlçatan deyil. Remote Control siyahısında bu qovluq yoxdur. |
| ChatGPT/Codex paylaşım linki | Şəbəkə siyasəti `chatgpt.com`-a icazə vermir. Link həm də hesaba giriş tələb edir. |
| GitHub hesabındakı repolar (`3dforma`, `Models`, `3ddesignst`) | MediaOS kodu yoxdur. |

**Qərar (istifadəçi təsdiqi ilə):** MEDIA OS AI sıfırdan quruldu. Ona görə də aşağıdakı cədvəl mövcud kodun auditi deyil, **yeni platformanın başlanğıc vəziyyətini** göstərir. Mövcud kod sonradan əlçatan olarsa, bu platforma ilə müqayisəli audit ayrıca aparılmalıdır (bax: FINAL_REPORT.md, "Qalan problemlər").

## 2. Komponentlərin vəziyyəti

| Komponent | Əvvəl (əlçatan kodda) | İndi | Qeyd |
|---|---|---|---|
| Docker | yox | `docker-compose.yml`: postgres+pgvector, redis, api, worker | Bu mühitdə Docker daemon yoxdur, ona görə compose işə salınıb yoxlanmayıb. Servislər birbaşa (native) işə salınıb sınaqdan keçirilib. |
| FastAPI | yox | `app/api/main.py`, 20 endpoint | Real HTTP (uvicorn) ilə yoxlanılıb |
| Frontend | yox | `frontend/` dashboard + AI Analyst çat | Playwright ilə yoxlanılıb, mobil ölçüdə üfüqi sürüşmə yoxdur |
| PostgreSQL | yox | PostgreSQL 16, 16 cədvəl + `schema_version` | Əsas həqiqət mənbəyidir |
| Redis | yox | Redis: keş, rate limit, qısamüddətli yaddaş | `maxmemory` + `allkeys-lru` |
| Worker/Scheduler | yox | `app/worker.py`: RSS kollektorları, saxlanma müddətinin təmizlənməsi | Real RSS lentləri konfiqurasiya edilməyib |
| AI xidmətləri | yox | LLM qatı: `local` / `anthropic` / `openai` | Real API açarı olmadığı üçün testlər `local` modellə aparılıb |
| News collectors | yox | `JsonFileCollector`, `RssCollector` | Bu mühitdən DGK saytına çıxış bloklanıb |
| Data pipeline | yox | Validation → Dedup → Relevance → PG → Classification ‖ Sentiment → Risk → Index | |
| RAG / vector store | yox | pgvector 0.6 (HNSW, cosine) | Seçimin səbəbi aşağıdadır |
| LangChain | yox | langchain-core 1.8: Chat Model, Messages, Prompt, Parser, Runnable, Loader, Splitter, Embeddings, Retriever, Tools | |

## 3. Vektor bazasının seçimi: pgvector

- PostgreSQL artıq əsas bazadır. Ayrıca vektor bazası əlavə etmək sinxronizasiya, backup və icazə yükünü ikiqat artırardı.
- Giriş icazəsi (`access_roles`) və təsdiq statusu (`approval_status`) **eyni SQL sorğusunda** süzülür. Ona görə icazəsiz sənəd heç vaxt LLM kontekstinə düşmür; ölçmədə sızma 0-dır.
- pgvector 0.6 PostgreSQL 16 ilə uyğundur və HNSW indeksi işləyir.
- Mövcud kodda işlək vektor bazası aşkar edilərsə, promptun tələbinə uyğun olaraq səbəbsiz əvəz edilməməlidir. `PgVectorRetriever` LangChain `BaseRetriever` interfeysindədir, ona görə başqa bir retriever ilə əvəzlənə bilər.

## 4. İş mühitinin məhdudiyyətləri (ölçmələrə təsiri)

| Məhdudiyyət | Təsiri | Həll |
|---|---|---|
| LLM API açarı yoxdur | Real model ilə keyfiyyət ölçülmədi | Oflayn `LocalAnalystModel` yazıldı. Bu model LangChain `BaseChatModel`-dir və eyni zəncirlərdə işləyir. Açar verildikdə `MEDIAOS_LLM_PROVIDER=anthropic` ilə eyni ölçmə təkrarlanır. |
| HuggingFace bloklanıb | Neyron embedding modeli yüklənmədi | `HashingEmbeddings` (söz kökü + simvol 4-qramları). Semantik sinonimləri tutmur. |
| DGK saytı bloklanıb | Real xəbər toplanmadı | Sintetik nümunə dəsti istifadə olundu; hər element `is_synthetic=true` və "(nümunə)" ilə işarələnib. |
| Docker daemon yoxdur | compose işə salınmadı | Eyni versiyalarla native servislərdə sınaq aparıldı. |
