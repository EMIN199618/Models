"""LLM çıxışlarının Pydantic sxemləri. Hər strukturlaşdırılmış cavab bunlarla yoxlanılır."""
from typing import Literal

from pydantic import BaseModel, Field

ContentType = Literal["official", "media", "public_opinion"]
Category = Literal[
    "customs_operations",      # gömrük əməliyyatları, keçid məntəqələri
    "smuggling",               # qaçaqmalçılıqla mübarizə
    "legislation",             # qanunvericilik, qaydalar
    "digital_services",        # e-gömrük, rəqəmsal xidmətlər
    "service_quality",         # xidmət keyfiyyəti, növbələr, şikayətlər
    "corruption_allegation",   # korrupsiya iddiaları
    "revenue_statistics",      # gəlirlər, statistika
    "international",           # beynəlxalq əməkdaşlıq
    "management",              # rəhbərlik, kadr
    "other",
]
Sentiment = Literal["positive", "neutral", "negative"]
RiskLevel = Literal["none", "low", "medium", "high", "critical"]  # none = maddi risk aşkarlanmayıb


class RelevanceOutput(BaseModel):
    is_relevant: bool = Field(description="Xəbər Azərbaycan Respublikasının Dövlət Gömrük Komitəsinə aiddirmi")
    score: float = Field(ge=0, le=1)
    content_type: ContentType = Field(description="official — DGK-nin rəsmi açıqlaması; media — jurnalist materialı; public_opinion — vətəndaş şikayəti/rəyi")
    reason: str
    confidence: float = Field(ge=0, le=1)
    # Relevance v2 — sübutlar (lüğət mühərriki doldurur; LLM də əlavə edə bilər)
    relevance_level: str | None = Field(default=None, description="DIRECT | CONTEXTUAL | WEAK | NONE")
    matched_keywords: list[str] = Field(default_factory=list)
    matched_entities: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    responsibility: str | None = Field(default=None, description="DGK | other_agency_possible | unknown")


class CategoryOutput(BaseModel):
    category: Category
    location: str | None = Field(default=None, description="Gömrük idarəsi / keçid məntəqəsi, varsa")
    confidence: float = Field(ge=0, le=1)


class SentimentOutput(BaseModel):
    sentiment: Sentiment = Field(description="Məzmunun DGK-yə münasibətdə tonallığı")
    score: float = Field(ge=-1, le=1)
    rationale: str
    confidence: float = Field(ge=0, le=1)


class RiskOutput(BaseModel):
    risk_level: RiskLevel
    score: float = Field(ge=0, le=1)
    criteria: list[str] = Field(default_factory=list, description="Uyğun gələn risk meyarlarının kodları")
    reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    claim_verified: bool = False
    requires_human_review: bool = False
    confidence: float = Field(ge=0, le=1)


class FactCheckOutput(BaseModel):
    status: Literal["confirmed", "contradicted", "unverified"]
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str
    confidence: float = Field(ge=0, le=1)


class RagAnswer(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list, description="Kontekstdəki mənbə identifikatorları, məs. S1")
    insufficient_evidence: bool = False
    confidence: float = Field(ge=0, le=1)


class SummaryPoint(BaseModel):
    text: str
    citations: list[str] = Field(default_factory=list)


class ExecutiveSummary(BaseModel):
    headline: str
    key_points: list[SummaryPoint]
    risks: list[SummaryPoint] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
