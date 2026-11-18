# Test nəticələri

**Tarix:** 2026-11-18 · **Pytest:** 98 keçdi, 0 uğursuz · **LLM:** local (oflayn evristika) · **Məlumat:** SİNTETİK

Bu nəticələr real DGK məlumatı və ya real LLM üzərində deyil. Real məlumatla ölçmə ROADMAP-ın 1-ci mərhələsindədir.

## Tələb olunan 8 ssenari

| # | Ssenari | Nəticə | Test |
|---|---|---|---|
| 1 | DGK-nın adi rəsmi məlumatı əsassız risk yaratmır | ✅ e-gömrük, terminal xəbərləri → risk yoxdur | `test_official_routine_news_has_no_risk` |
| 2 | Mənfi, təsdiqlənməmiş şərh avtomatik yüksək risk olmur | ✅ meyarsız mənfi rəy → low. Rüşvət iddiası → high, amma `claim_verified=false` və insan yoxlamasına gedir | `test_sentiment_and_risk_are_independent`, `test_rule_validation_*` |
| 3 | DGK sözü yoxdur, amma gömrük fəaliyyəti var | ✅ "Astara gömrük postunda gecikmə" → qəbul; "Astara keçidində sənəd yoxlaması uzun çəkir" → yoxlanmalıdır | `test_relevance_v2_scenarios` |
| 4 | Başqa ölkənin gömrüyü DGK-ya aid edilmir | ✅ Qazaxıstan, Kapıkule (türkcə), Gürcüstan, Rusiya FTS | `test_relevance_v2_scenarios`, `test_relevance_rejects_foreign_customs` |
| 5 | Eyni hadisə müxtəlif mənbələrdə | ⚠ Demək olar eyni mətn birləşir (simhash). Fərqli sözlərlə yazılmış nüsxələrin hadisə kartında birləşdirilməsi hələ yoxdur | `test_duplicate_not_in_feed` |
| 6 | Şəkildəki gömrük mətni OCR ilə | ✅ Real Tesseract "DÖVLƏT GÖMRÜK KOMİTƏSİ" yazısını oxuyur → qəbul | `test_ocr_reads_customs_text_from_image` |
| 7 | Videoda gömrük mövzusu | ⚠ Transkript verildikdə vaxt nişanı ilə tapılır (41.5 s). Lokal speech-to-text qoşulmayıb | `test_video_transcript_timestamps` |
| 8 | Mənbəyə giriş yoxdursa açıq göstərilir | ✅ EnsembleData token/limit xətaları, büdcə limiti. customs.gov.az-ın bloklanması PROGRESS.md-də | `test_api_errors_mapped_*`, `test_budget_cap_stops_calls` |

## Relevance v2 ssenariləri (19)

Hamısı keçir: rəsmi xəbər; Astara + məktəb; gömrük postu; semantik; Qazaxıstan; Kapıkule; rəhbər + struktur; eyniadlı şəxs; idxal; rus dili (×2); ingilis; domen; zəif söz + yer (liman, polis, aksiz); Gömrükçü klubu; pasport/DSX; Ağbənd.

## Keyfiyyət ölçmələri (`python -m eval.run_eval`)

| Göstərici | İnkişaf dəsti (45) | Hold-out (16, tənzimlənməyib) |
|---|---|---|
| DGK relevance F1 | 1.0 | **0.9565** |
| Məzmun növü dəqiqliyi | 1.0 | **1.0** |
| Kateqoriya dəqiqliyi | 0.8889 | **0.6364** |
| Sentiment macro-F1 | 0.8286 | **0.813** |
| Risk dəqiqliyi | 0.9722 (FP: n07) | **1.0** |

Hold-out səhvləri: h02: category digital_services->service_quality; h05: sentiment positive->neutral; h09: category customs_operations->international; h10: category service_quality->other; h12: relevance False; h14: category international->customs_operations; h16: sentiment negative->neutral

Qeyd: inkişaf dəsti qaydalar yazılarkən istifadə olunub, ona görə onun göstəriciləri optimistdir. Kateqoriya təsnifatı zəif yerdir və real LLM tələb edir.

| RAG / Agent / Keş | Nəticə |
|---|---|
| RAG recall@4 / MRR | 1.0 / 0.8148 |
| Mənbəli cavab / düzgün imtina | 1.0 / 1.0 |
| İcazəsiz sənəd sızması | 0 |
| Agent: alət seçimi / alət uğuru | 1.0 / 1.0 |
| Redis hit rate | 0.975 |
| API p50: Redis ilə / Redis-siz | 11.05 ms / 14.51 ms |

## Yaradılmayan testlər (səbəbi ilə)

- **Vision analysis:** Vision modeli qoşulmayıb.
- **Comment clustering:** funksiya hələ yoxdur.
- **Playwright e2e:** brauzerlə əl ilə yoxlanılıb (konsol xətası yoxdur, mobil ölçüdə üfüqi sürüşmə yoxdur), amma CI testi yazılmayıb.

## Pytest siyahısı

**test_agent.py** (17)

- test_example_questions[Bu g\xfcn DGK haqq\u0131nda hans\u0131 x\u0259b\u0259rl\u0259r yay\u0131mlan\u0131b?-expected_tools0]
- test_example_questions[Son 7 g\xfcnd\u0259 m\u0259nfi r\u0259yl\u0259r hans\u0131 m\xf6vzularla ba\u011fl\u0131d\u0131r?-expected_tools1]
- test_example_questions[Astara g\xf6mr\xfcy\xfc haqq\u0131nda \u015fikay\u0259tl\u0259ri g\xf6st\u0259r.-expected_tools2]
- test_example_questions[Q\u0131rm\u0131z\u0131 K\xf6rp\xfcd\u0259 \u0259m\u0259kda\u015f\u0131n pul t\u0259l\u0259b etm\u0259si \u0259vv\u0259l d\u0259 yay\u0131mlan\u0131b?-expected_tools3]
- test_example_questions[Q\u0131rm\u0131z\u0131 K\xf6rp\xfcd\u0259 r\xfc\u015fv\u0259t t\u0259l\u0259b olunmas\u0131 iddias\u0131 r\u0259smi m\u0259nb\u0259d\u0259 t\u0259sdiql\u0259nib?-expected_tools4]
- test_example_questions[Son bir ayda g\xf6mr\xfck f\u0259aliyy\u0259tin\u0259 dair \u0259sas ictimai naraz\u0131l\u0131qlar hans\u0131lard\u0131r?-expected_tools5]
- test_example_questions[DGK r\u0259hb\u0259rliyi \xfc\xe7\xfcn g\xfcnd\u0259lik analitik icmal haz\u0131rla.-expected_tools6]
- test_fact_check_detects_official_denial
- test_negative_topics_question_returns_cited_items
- test_permission_denied_for_viewer
- test_schema_validation_rejects_bad_args
- test_tool_timeout
- test_tool_calls_are_audited
- test_agent_has_no_write_tools
- test_report_requires_human_approval
- test_high_risk_signal_requires_confirmation
- test_ai_answer_cache_is_per_user

**test_api.py** (9)

- test_health
- test_auth_required_and_roles
- test_rate_limit_returns_429
- test_irrelevant_news_never_in_feed
- test_content_types_are_separated
- test_duplicate_not_in_feed
- test_news_detail_shows_prompt_versions
- test_metrics_endpoint
- test_prompts_listing

**test_cache.py** (7)

- test_get_or_set_hit_miss_and_invalidation
- test_ttl_is_applied
- test_user_scopes_are_isolated
- test_rate_limit_redis_and_local_fallback
- test_redis_down_falls_back_to_postgres
- test_dashboard_cache_and_invalidation_on_new_data
- test_cache_info_reports_policy_and_hit_rate

**test_chains.py** (13)

- test_chains_are_lcel_runnables
- test_relevance_rejects_foreign_customs
- test_relevance_accepts_dgk_and_separates_content_type
- test_input_validation
- test_sentiment_and_risk_are_independent
- test_prompt_injection_in_source_is_treated_as_data
- test_rule_validation_downgrades_and_strips_evidence
- test_corruption_allegation_is_high_and_needs_review
- test_retry_then_fallback_and_metrics
- test_structured_step_safe_default_on_failure
- test_all_prompts_versioned_and_render
- test_tool_calling_messages_roles
- test_fact_check_does_not_match_different_location

**test_ensembledata.py** (11)

- test_parse_and_dedup_within_run
- test_full_pipeline_relevance_risk_and_virality
- test_feed_shows_platform_and_masks_private_handles
- test_budget_cap_stops_calls
- test_api_errors_mapped_and_token_redacted[491-AuthError]
- test_api_errors_mapped_and_token_redacted[493-AuthError]
- test_api_errors_mapped_and_token_redacted[495-QuotaError]
- test_token_never_logged_or_returned
- test_admin_endpoints
- test_invalid_token_rejected
- test_malformed_token_gives_clear_message

**test_memory.py** (5)

- test_follow_up_question_uses_short_term_context
- test_other_user_cannot_read_or_continue_conversation
- test_long_term_memory_requires_approval_and_rejects_pii
- test_retention_purge_expires_old_items
- test_memory_layers_are_separate

**test_rag.py** (8)

- test_retrieves_relevant_official_document
- test_viewer_cannot_see_internal_document_but_analyst_can
- test_pending_document_is_never_retrieved
- test_rag_answer_is_grounded_with_valid_citations
- test_rag_reports_missing_information_instead_of_inventing
- test_source_validation_strips_fabricated_citations
- test_answer_without_any_valid_source_is_flagged
- test_semantic_search_endpoint_cached_per_role

**test_structure.py** (28)

- test_relevance_v2_scenarios[DGK r\u0259smi x\u0259b\u0259ri]
- test_relevance_v2_scenarios[Astara \u2014 \u0259laq\u0259siz]
- test_relevance_v2_scenarios[post, DGK abbr. yoxdur]
- test_relevance_v2_scenarios[semantik, a\xe7ar s\xf6z yoxdur]
- test_relevance_v2_scenarios[ba\u015fqa \xf6lk\u0259]
- test_relevance_v2_scenarios[t\xfcrkc\u0259 Kap\u0131kule]
- test_relevance_v2_scenarios[r\u0259hb\u0259r + struktur]
- test_relevance_v2_scenarios[eyniadl\u0131 \u015f\u0259xs]
- test_relevance_v2_scenarios[yaln\u0131z idxal]
- test_relevance_v2_scenarios[rus dili]
- test_relevance_v2_scenarios[rus \u2014 m\u0259nt\u0259q\u0259]
- test_relevance_v2_scenarios[ingilis]
- test_relevance_v2_scenarios[domen]
- test_relevance_v2_scenarios[z\u0259if + yer: liman]
- test_relevance_v2_scenarios[z\u0259if + yer: polis]
- test_relevance_v2_scenarios[z\u0259if + yer: aksiz]
- test_relevance_v2_scenarios[G\xf6mr\xfck\xe7\xfc klubu]
- test_relevance_v2_scenarios[pasport \u2014 DSX]
- test_relevance_v2_scenarios[A\u011fb\u0259nd infrastruktur]
- test_lexicon_loaded_from_db
- test_old_news_maps_to_position_at_publication_date
- test_structure_endpoint
- test_person_page_has_no_reputation_score
- test_keyword_management_and_audit
- test_official_routine_news_has_no_risk
- test_ocr_reads_customs_text_from_image
- test_video_transcript_timestamps
- test_ssrf_guard_blocks_private_and_unlisted_hosts
