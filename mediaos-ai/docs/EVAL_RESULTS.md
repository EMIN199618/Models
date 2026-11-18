# MEDIA OS AI — Ölçmə nəticələri

> **Məlumat:** SİNTETİK nümunə dəsti (45 xəbər, 11 RAG sualı, 12 agent sualı). Real DGK məlumatı üzərində keyfiyyət ölçülməyib — bunun üçün qızıl etiketli real nümunə lazımdır.
> **LLM:** `local` / `local-heuristic-v1`; embeddings: `hashing`. **Tarix:** 2026-11-18T16:06:05+00:00

## 1. Təsnifat (Chain 1–3)
| Göstərici | Nəticə |
|---|---|
| DGK relevance precision / recall / F1 | 1.0 / 1.0 / 1.0 |
| Məzmun növü (official/media/public_opinion) dəqiqliyi | 1.0 |
| Kateqoriya dəqiqliyi | 0.8889 |
| Sentiment macro-F1 | 0.8286 |
| Risk dəqiqliyi | 0.9722 |
| Risk yanlış pozitivləri (FP / nisbət) | 1 / 0.0278 — n07 |
| Risk yanlış neqativləri | 0 — — |
| High-risk precision / recall | 0.8 / 1.0 |
| Prompt injection nümunəsi (n39) risk nəticəsi | low (gözlənilən: low) |
| Pipeline sürəti | 23.4 xəbər/san (1.92 s) |

### Hold-out dəst (evristikalar bu dəstə baxılmadan yazılıb — daha dürüst göstərici)
| Göstərici | Nəticə |
|---|---|
| Relevance precision / recall / F1 | 1.0 / 0.9167 / 0.9565 |
| Məzmun növü dəqiqliyi | 1.0 |
| Kateqoriya dəqiqliyi | 0.6364 |
| Sentiment macro-F1 | 0.813 |
| Risk dəqiqliyi | 1.0 (FP: —; FN: —) |

Hold-out səhvləri: h02: category digital_services->service_quality; h05: sentiment positive->neutral; h09: category customs_operations->international; h10: category service_quality->other; h12: relevance False; h14: category international->customs_operations; h16: sentiment negative->neutral

> Qeyd: əsas dəst (45 xəbər) həm də inkişaf dəsti kimi istifadə olunub, ona görə onun göstəriciləri optimistdir.

## 2. RAG (Chain 4)
| Göstərici | Nəticə |
|---|---|
| Retrieval precision@4 | 0.4167 |
| Retrieval recall@4 | 1.0 |
| MRR | 0.8148 |
| Mənbəyə əsaslanan cavab nisbəti | 1.0 |
| Düzgün imtina (məlumat yoxdursa) | 1.0 |
| Gözlənilən fakt cavabda | 1.0 |
| İcazəsiz daxili sənəd sızması (viewer) | 0 |
| Təsdiqlənməmiş sənəd sızması | 0 |

## 3. AI Analyst agent (tool-calling)
| Göstərici | Nəticə |
|---|---|
| Alət seçimi dəqiqliyi | 1.0 |
| Alət çağırışı uğur faizi | 1.0 ({'ok': 14}) |
| İstinadlı cavab nisbəti | 0.9167 |
| Silinmiş uydurma istinad | 0 |
| Çat latency p50 / p95 | 57.53 ms / 78.3 ms |

## 4. Redis keş və API latency
| Göstərici | Redis ilə | Redis nasaz (yalnız PostgreSQL) |
|---|---|---|
| API latency p50 | 9.9 ms | 14.04 ms |
| API latency p95 | 14.43 ms | 24.84 ms |
| Cache hit rate | 0.975 (234 hit / 6 miss) | — |
| Bütün sorğular uğurlu | bəli | bəli |

Redis: maxmemory=134217728, policy=allkeys-lru, evicted_keys=0

Marşrut üzrə (Redis ilə / Redis-siz) p50:

- `/api/dashboard/stats`: 9.88 ms / 18.82 ms
- `/api/news/latest`: 9.99 ms / 12.62 ms
- `/api/search`: 9.76 ms / 11.97 ms

## 5. LLM istifadəsi
| Zəncir | Çağırış | Input token | Output token | Xərc (USD) | Orta latency | Xəta |
|---|---|---|---|---|---|---|
| agent | 24 | 11701 | 3129 | 0.0 | 0.44 ms | 0 |
| report | 1 | 687 | 132 | 0.0 | 0.58 ms | 0 |
| classification | 94 | 46904 | 2318 | 0.0 | 0.26 ms | 0 |
| rag | 11 | 8689 | 1330 | 0.0 | 0.61 ms | 0 |
| relevance | 61 | 38361 | 2131 | 0.0 | 0.31 ms | 0 |
| risk | 47 | 49789 | 2149 | 0.0 | 0.65 ms | 0 |
| factcheck | 2 | 1467 | 69 | 0.0 | 0.77 ms | 0 |

Local provayderdə xərc 0-dır; token sayı simvol/4 təxmini ilə hesablanır. Real provayderdə token sayı API cavabından götürülür.

## Prompt versiyaları

- `dgk_relevance` 1.2.0
- `news_category` 1.1.0
- `sentiment` 1.1.0
- `risk_assessment` 1.3.0
- `fact_check` 1.0.0
- `rag_qa` 1.2.0
- `executive_summary` 1.1.0
- `analyst_agent` 1.1.0
