"""Mərkəzi konfiqurasiya. Bütün dəyərlər mühit dəyişənlərindən (MEDIAOS_*) oxunur."""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDIAOS_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"

    # --- PostgreSQL (əsas mənbə) ---
    database_url: str = "postgresql+psycopg://mediaos:mediaos@localhost:5432/mediaos"

    # --- Redis (yalnız sürət qatı; nasaz olsa sistem PostgreSQL ilə davam edir) ---
    redis_url: str = "redis://localhost:6379/0"
    redis_socket_timeout: float = 0.25
    cache_ttl_dashboard: int = 60
    cache_ttl_latest_news: int = 30
    cache_ttl_search: int = 300
    cache_ttl_ai_answer: int = 120
    rate_limit_per_minute: int = 60
    rate_limit_chat_per_minute: int = 20

    # --- LLM qatı ---
    # local    — deterministik, oflayn evristik model (test və API açarı olmadıqda)
    # anthropic / openai — real provayderlər
    llm_provider: Literal["local", "ollama", "anthropic", "openai"] = "local"
    llm_model: str = "claude-opus-5-5"
    # Anthropic API ünvanı açıq verilir ki, mühitdəki ANTHROPIC_BASE_URL sorğuları başqa yerə yönəltməsin
    anthropic_base_url: str = "https://api.anthropic.com"
    # Düşünmə həmişə aktivdir (Opus 5.5) — thinking tokenləri də bu limitə daxildir
    llm_max_tokens: int = 16000
    llm_fallback_provider: Literal["none", "local"] = "local"
    # --- Lokal LLM (Ollama) — demo üçün. 16 GB RAM + NVIDIA GPU üçün 7–8B, 4-bit model tövsiyə olunur ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_num_ctx: int = 8192          # kontekst pəncərəsi (VRAM istifadəsinə birbaşa təsir edir)
    ollama_keep_alive: str = "10m"      # boş qaldıqda model yaddaşdan çıxarılır (RAM/VRAM azad olur)
    ollama_timeout_s: float = 120.0     # lokal model API-dən yavaşdır
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 2
    llm_temperature: float = 0.0
    # 1M token üçün təxmini qiymət (USD) — xərc hesabatı üçün
    llm_cost_input_per_mtok: float = 4.0    # claude-opus-5-5
    llm_cost_output_per_mtok: float = 20.0

    embedding_provider: Literal["hashing", "openai"] = "hashing"
    embedding_dim: int = 384

    # --- RAG ---
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_top_k: int = 8
    rag_final_k: int = 4
    rag_min_score: float = 0.12

    # --- Keyfiyyət hədləri ---
    review_confidence_threshold: float = 0.6

    # --- Agent ---
    tool_timeout_s: float = 10.0
    agent_max_steps: int = 5

    # --- Yaddaş ---
    short_term_max_messages: int = 12
    short_term_ttl_s: int = 3600
    long_term_retention_days: int = 365
    chat_history_retention_days: int = 90

    # --- Collector ---
    collector_feeds: list[str] = Field(default_factory=list)
    collector_interval_s: int = 600

    # --- EnsembleData (Instagram + TikTok) ---
    # Token admin paneldən (DB-də saxlanılır) və ya bu dəyişənlə verilir. Heç vaxt loga yazılmır.
    ensembledata_token: str = ""
    ensembledata_base_url: str = "https://ensembledata.com/apis"
    ensembledata_timeout_s: float = 40.0
    # Bir toplama dövründə xərclənə biləcək maksimum unit (büdcə qoruyucusu)
    ensembledata_max_units_per_run: int = 150
    ensembledata_interval_s: int = 3600
    ed_tiktok_keywords: list[str] = Field(default_factory=lambda: [
        "Dövlət Gömrük Komitəsi", "DGK gömrük", "gömrük", "gomruk", "Astara gömrük", "Qırmızı körpü gömrük",
    ])
    ed_tiktok_hashtags: list[str] = Field(default_factory=lambda: ["gömrük", "gomruk", "dgk", "azerbaijancustoms"])
    ed_tiktok_period_days: Literal["0", "1", "7", "30", "90", "180"] = "7"
    ed_tiktok_country: str = ""
    ed_tiktok_official_accounts: list[str] = Field(default_factory=list)
    ed_tiktok_media_accounts: list[str] = Field(default_factory=list)
    ed_instagram_official_accounts: list[str] = Field(default_factory=list)
    ed_instagram_media_accounts: list[str] = Field(default_factory=list)
    ed_instagram_posts_per_account: int = 10
    ed_instagram_comment_posts: int = 3   # rəsmi hesabın neçə son postunun şərhləri toplansın
    # Viral hədləri — aşıldıqda risk meyarı R6 (geniş yayılma) tətbiq olunur
    ed_viral_views: int = 50_000
    ed_viral_shares: int = 500
    # Fərdi istifadəçilərin hesab adları dashboard-da maskalanır (rəsmi/media hesabları açıq göstərilir)
    ed_mask_user_handles: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
