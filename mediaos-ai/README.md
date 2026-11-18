# MEDIA OS AI

Dövlət Gömrük Komitəsi (DGK) üçün AI dəstəkli media monitorinqi platforması. Əsas funksiyalar:
- semantik axtarış və bilik bazası (RAG);
- yaddaş;
- AI Analyst agenti.

**Texnologiyalar:** FastAPI · PostgreSQL 16 + pgvector · Redis · LangChain (LCEL)

**Sənədlər:**
- [Audit](docs/AUDIT.md)
- [Arxitektura planı](docs/ARCHITECTURE.md)
- [Ölçmə nəticələri](docs/EVAL_RESULTS.md)
- [Yekun hesabat](docs/FINAL_REPORT.md)

## Docker ilə işə salma

```bash
cp backend/.env.example backend/.env
```

```bash
docker compose up -d --build
```

```bash
docker compose exec api python -m scripts.seed
```

Dashboard: http://localhost:8000. Dev tokenləri: `mos_dev_admin_token`, `mos_dev_analyst_token`, `mos_dev_viewer_token`.

> `scripts.seed` bazaya **sintetik** nümunə məlumatı və dev istifadəçiləri yazır. Production-da işlətməyin.

## Docker-siz işə salma

PostgreSQL 16 (pgvector extension ilə) və Redis lazımdır.

```bash
cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```

```bash
python -m scripts.seed --reset
```

```bash
uvicorn app.api.main:app --port 8000
```

```bash
python -m app.worker
```

## Real LLM qoşmaq

`backend/.env` faylında:

```
MEDIAOS_LLM_PROVIDER=anthropic
MEDIAOS_LLM_MODEL=claude-sonnet-5-5
ANTHROPIC_API_KEY=...
```

Açar olmadıqda sistem `local` (oflayn, deterministik) modellə işləyir. Real provayder xəta verəndə də avtomatik `local` modelə keçir.

## Testlər və ölçmə

Testlər üçün ayrıca `mediaos_test` bazası lazımdır. Ölçmə skripti isə `mediaos_eval` bazasından istifadə edir.

```bash
cd backend && python -m pytest -q
```

```bash
python -m eval.run_eval
```

Ölçmə nəticələri `eval/results/latest.json` və `docs/EVAL_RESULTS.md` fayllarına yazılır.

## Nümunə suallar (AI Analyst)

- Bu gün DGK haqqında hansı xəbərlər yayımlanıb?
- Son 7 gündə mənfi rəylər hansı mövzularla bağlıdır?
- Astara gömrüyü haqqında şikayətləri göstər.
- Bu məlumat əvvəl də yayımlanıb?
- Bu iddia rəsmi mənbədə təsdiqlənib?
- Son bir ayda gömrük fəaliyyətinə dair əsas ictimai narazılıqlar hansılardır?
- DGK rəhbərliyi üçün gündəlik analitik icmal hazırla.
