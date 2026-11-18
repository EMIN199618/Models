"""Oflayn, deterministik analitik məntiq (local provayder).

Məqsəd: API açarı olmadan bütün zəncirlərin real işləməsi, test edilə bilməsi və real LLM
nəticələri üçün baza xətti (baseline). Real provayder seçiləndə bu modul yalnız
fallback kimi istifadə olunur.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.text import normalize_az, stems, tokens

# ---------------------------------------------------------------- leksikonlar
AZ_LOCATIONS = {
    "astara": "Astara", "biləsuvar": "Biləsuvar", "qırmızı körpü": "Qırmızı Körpü", "sədərək": "Sədərək",
    "yalama": "Yalama", "balakən": "Balakən", "ələt": "Ələt", "culfa": "Culfa", "horadiz": "Horadiz",
    "heydər əliyev beynəlxalq hava limanı": "Heydər Əliyev Hava Limanı", "hava limanı": "Hava limanı",
    "bakı limanı": "Bakı Limanı", "dəniz limanı": "Bakı Limanı", "laçın": "Laçın", "zəngilan": "Zəngilan",
    "naxçıvan": "Naxçıvan", "gəncə": "Gəncə",
}

STRONG_DGK = [
    r"dövlət gömrük komitə", r"\bdgk\b", r"gömrük komitəsi", r"azərbaycan(ın)? gömrük",
    r"gömrük (post|idarə|keçid|orqan|əməkdaş|xidmət|rüsum|bəyannamə|ərazi|nəzarət|məntəqə|terminal|yoxlama|rəsmiləşdir)",
    r"e-gömrük", r"sərhəd-keçid", r"gömrükçü",
    # rus dilində
    r"таможенн\w* комитет", r"\bгтк\b", r"таможн\w* азербайджан", r"азербайджанск\w* таможн",
]
MEDIUM_DGK = [r"gömrü[kyğ]", r"qaçaqmal", r"bəyannamə", r"rüsum", r"aksiz", r"tranzit yük",
              r"таможн", r"контрабанд", r"растаможк"]
FOREIGN_CUSTOMS = re.compile(
    r"(gürcüstan|rusiya|türkiyə|iran|qazaxıstan|özbəkistan|avropa|abş|çin|ukrayna|almaniya|fransa)"
    r"\w*\s+(\w+\s+)?(gömrü|federal gömrük|gəlirlər)"
)
AZ_CONTEXT = re.compile(r"azərbaycan|azerbaycan|dgk|dövlət gömrük komitə|азербайджан|гтк|" + "|".join(AZ_LOCATIONS))
NOISE = [r"gömrük ittifaqı", r"futbol", r"hava proqnozu", r"konsert", r"serial"]

CATEGORY_KW: dict[str, list[str]] = {
    "smuggling": ["qaçaqmal", "narkotik", "müsadirə", "saxlanıl", "aşkarla", "gizlədil", "kontrabanda"],
    "legislation": ["qanun", "qərar", "məcəllə", "qaydalar", "dəyişiklik", "normativ", "fərman", "tarif"],
    "digital_services": ["e-gömrük", "elektron", "rəqəmsal", "onlayn", "mobil tətbiq", "portal", "avtomatlaş", "smart"],
    "service_quality": ["növbə", "gözlə", "şikayət", "narazı", "süründürmə", "kobud", "xidmət keyfiyyəti", "saatlarla", "gecik"],
    "corruption_allegation": ["rüşvət", "korrupsiya", "pul tələb", "qanunsuz ödəniş", "vəzifədən sui-istifadə"],
    "revenue_statistics": ["milyon manat", "milyard", "büdcə", "gəlir", "statistika", "faiz artıb", "rüsum daxilolma", "proqnoz"],
    "international": ["beynəlxalq", "dünya gömrük təşkilatı", "əməkdaşlıq", "memorandum", "xarici həmkar", "saziş"],
    "management": ["sədr", "təyin", "rəhbər", "kollegiya", "kadr", "vəzifəyə"],
    "customs_operations": ["keçid", "yük", "terminal", "tranzit", "rəsmiləşdir", "nəzarət", "yoxlama", "post"],
}

NEG_WORDS = [
    "şikayət", "narazı", "süründürmə", "rüşvət", "korrupsiya", "gecik", "saatlarla", "kobud", "problem",
    "əziyyət", "tənqid", "qanunsuz", "ədalətsiz", "biabırçı", "dözülməz", "pul tələb", "təhqir", "laqeyd",
    "uzun növbə", "əsassız", "itirdik", "zərər", "xaos",
]
POS_WORDS = [
    "təşəkkür", "uğur", "asanlaşdır", "sürətləndir", "müasir", "mükafat", "rahat", "operativ", "peşəkar",
    "yüksək qiymətləndir", "təkmilləşdir", "şəffaf", "qarşısı alın", "müsadirə", "aşkarla", "zərərsizləşdir",
    "artım", "yeni xidmət", "istifadəyə veril",
]
INTERDICTION = ["qarşısı alın", "müsadirə", "aşkarla", "saxlanıl", "zərərsizləşdir", "ələ keçiril"]

RISK_CRITERIA: dict[str, tuple[str, list[str]]] = {
    "R1": ("Korrupsiya/rüşvət iddiası", ["rüşvət", "korrupsiya", "pul tələb", "qanunsuz ödəniş", "pul istə"]),
    "R2": ("Hüquq pozuntusu iddiası", ["qanunsuz", "hüquq pozuntu", "vəzifədən sui-istifadə", "saxtakarlıq", "cinayət işi açıl"]),
    "R3": ("Sistemli/kütləvi narazılıq", ["hamı", "hər gün", "kütləvi", "yüzlərlə", "onlarla sürücü", "dəfələrlə", "daim", "petisiya"]),
    "R4": ("Təhlükəsizlik insidenti", ["partlayış", "yanğın", "silahlı", "yaralan", "həlak", "insident", "kiberhücum", "məlumat sızması"]),
    "R5": ("Rəhbərliyə yönəlmiş ittiham", ["sədr", "rəhbərlik", "rəisi", "komitə rəhbəri"]),
}
DENIAL = ["təkzib", "həqiqətə uyğun deyil", "əsassızdır", "yalan", "reallığı əks etdirmir", "doğru deyil"]

# ------------------------------------------------------------------ köməkçilər
_FOLD = str.maketrans({"ə": "e", "ö": "o", "ü": "u", "ğ": "g", "ı": "i", "ş": "s", "ç": "c"})


def fold(text: str) -> str:
    """Sosial şəbəkədə tez-tez xüsusi hərfsiz yazılır ("gomruk", "qacaqmalciliq"). Hər iki yazılış tutulur.
    Türk dilindəki "gümrük" → "gumruk" olur və "gomruk"-a uyğun gəlmir (Türkiyə gömrüyü səhvən tutulmur)."""
    return text.translate(_FOLD)


def _count(text: str, pats: list[str]) -> int:
    ft = fold(text)
    return sum(1 for p in pats if re.search(p, text) or re.search(fold(p), ft))


def _hits(text: str, words: list[str]) -> list[str]:
    ft = fold(text)
    return [w for w in words if w in text or fold(w) in ft]


def find_location(text: str) -> str | None:
    t = normalize_az(text)
    ft = fold(t)
    for k, v in AZ_LOCATIONS.items():
        if k in t or fold(k) in ft:
            return v
    return None


# ------------------------------------------------------------------ tapşırıqlar
def relevance(title: str, body: str, source_kind: str) -> dict[str, Any]:
    t = normalize_az(f"{title} {body}")
    strong, medium = _count(t, STRONG_DGK), _count(t, MEDIUM_DGK)
    score = min(1.0, 0.45 * strong + 0.18 * medium)
    loc = find_location(t)
    if loc and medium:
        score += 0.45  # Azərbaycan gömrük postunun adı + gömrük sözü = güclü siqnalla eyni çəki ("Astara gömrüyü")
    reasons = []
    if (FOREIGN_CUSTOMS.search(t) or FOREIGN_CUSTOMS.search(fold(t))) and not (AZ_CONTEXT.search(t) or AZ_CONTEXT.search(fold(t))):
        score -= 0.6
        reasons.append("xarici ölkənin gömrük orqanı haqqındadır")
    if _count(t, NOISE):
        score -= 0.4
        reasons.append("mövzu gömrüklə əlaqəsizdir")
    if source_kind == "official" and medium:
        score += 0.15
    score = max(0.0, min(1.0, score))
    is_rel = score >= 0.5
    if is_rel:
        reasons.insert(0, f"DGK göstəriciləri: {strong} güclü, {medium} orta" + (f"; yer: {loc}" if loc else ""))
    elif not reasons:
        reasons.append("DGK-yə birbaşa istinad tapılmadı")
    conf = round(min(0.95, 0.5 + abs(score - 0.5) * 1.2), 3)

    if source_kind == "official":
        ctype = "official"
    elif source_kind in ("complaint", "social") or re.search(
        r"\b(mən|biz|bizi|məni|gözlədik|şikayət edirəm|şikayətimi|sürücüyəm)\b", t
    ):
        ctype = "public_opinion"
    else:
        ctype = "media"
    return {"is_relevant": is_rel, "score": round(score, 3), "content_type": ctype,
            "reason": "; ".join(reasons), "confidence": conf}


def category(title: str, body: str) -> dict[str, Any]:
    t = normalize_az(f"{title} {body}")
    scores = {c: len(_hits(t, kws)) for c, kws in CATEGORY_KW.items()}
    # Korrupsiya iddiası digər kateqoriyalardan üstündür
    if scores["corruption_allegation"]:
        scores["corruption_allegation"] += 2
    best = max(scores, key=lambda c: scores[c])
    total = sum(scores.values())
    if scores[best] == 0:
        return {"category": "other", "location": find_location(t), "confidence": 0.4}
    conf = round(min(0.95, 0.45 + 0.5 * scores[best] / max(total, 1)), 3)
    return {"category": best, "location": find_location(t), "confidence": conf}


def sentiment(title: str, body: str, content_type: str) -> dict[str, Any]:
    t = normalize_az(f"{title} {body}")
    neg, pos = _hits(t, NEG_WORDS), _hits(t, POS_WORDS)
    interdiction = _hits(t, INTERDICTION)
    score = 0.25 * len(pos) - 0.3 * len(neg)
    if interdiction and not _hits(t, ["rüşvət", "korrupsiya", "şikayət"]):
        score = max(score, 0.3)  # uğurlu əməliyyat DGK-yə münasibətdə müsbətdir
    if content_type == "official" and not neg:
        score = max(score, 0.1)
    score = max(-1.0, min(1.0, score))
    label = "positive" if score >= 0.2 else "negative" if score <= -0.2 else "neutral"
    rationale = (f"mənfi işarələr: {', '.join(neg[:4]) or '—'}; müsbət işarələr: {', '.join(pos[:4]) or '—'}")
    conf = round(min(0.95, 0.55 + 0.1 * (len(neg) + len(pos))), 3) if (neg or pos) else 0.6
    return {"sentiment": label, "score": round(score, 3), "rationale": rationale, "confidence": conf}


def parse_context(ctx: str) -> list[dict[str, str]]:
    """'[S1] (doc_type=..; source=..; date=..)\\nmətn' bloklarını parse edir."""
    blocks = []
    for raw in re.split(r"\n---\n", ctx.strip()):
        m = re.match(r"\[([A-Z]\d+)\]\s*\(([^)]*)\)\s*\n?(.*)", raw.strip(), re.S)
        if not m:
            continue
        meta = dict(kv.split("=", 1) for kv in m.group(2).split("; ") if "=" in kv)
        blocks.append({"id": m.group(1), "text": m.group(3).strip(), **meta})
    return blocks


def _overlap(a: str, b: str) -> float:
    sa, sb = stems(a), stems(b)
    return len(sa & sb) / max(1, len(sa))


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", text))


def fact_check(claim: str, evidence: str) -> dict[str, Any]:
    blocks = [b for b in parse_context(evidence) if b.get("doc_type", "").startswith(("official", "legislation"))]
    best, best_ov = None, 0.0
    claim_loc = find_location(claim)
    for b in blocks:
        # Fərqli yerdəki hadisə eyni hadisə deyil (məs. Balakən iddiası ≠ Qırmızı Körpü təkzibi)
        ev_loc = find_location(b["text"] + " " + b.get("title", ""))
        if claim_loc and ev_loc and claim_loc != ev_loc:
            continue
        ov = _overlap(claim, b["text"])
        if ov > best_ov:
            best, best_ov = b, ov
    if not best or best_ov < 0.3:
        return {"status": "unverified", "evidence_ids": [], "confidence": 0.7,
                "explanation": "Rəsmi mənbələrdə bu iddianı təsdiq və ya təkzib edən məlumat tapılmadı."}
    bt = normalize_az(best["text"])
    if _hits(bt, DENIAL) and best_ov >= 0.4:
        return {"status": "contradicted", "evidence_ids": [best["id"]], "confidence": round(min(0.9, 0.5 + best_ov), 3),
                "explanation": f"Rəsmi mənbə [{best['id']}] iddianı təkzib edir."}
    cn, en = _numbers(claim), _numbers(best["text"])
    if cn and not (cn & en):
        return {"status": "unverified", "evidence_ids": [best["id"]], "confidence": 0.55,
                "explanation": f"Mövzu [{best['id']}] mənbəsində var, amma iddiadakı rəqəmlər rəsmi məlumatla üst-üstə düşmür."}
    if best_ov >= 0.45:
        return {"status": "confirmed", "evidence_ids": [best["id"]], "confidence": round(min(0.92, 0.4 + best_ov), 3),
                "explanation": f"Rəsmi mənbə [{best['id']}] iddianın əsas məzmununu təsdiqləyir."}
    return {"status": "unverified", "evidence_ids": [best["id"]], "confidence": 0.5,
            "explanation": f"[{best['id']}] qismən oxşardır, lakin birbaşa təsdiq yoxdur."}


def risk(title: str, body: str, content_type: str, sentiment_label: str, mentions: int, evidence: str,
         reach: str = "") -> dict[str, Any]:
    t = normalize_az(f"{title} {body}")
    criteria, reasons = [], []
    # DGK-nin uğurlu əməliyyatı (qaçaqmalçılığın qarşısının alınması) DGK üçün risk deyil
    interdiction = bool(_hits(t, INTERDICTION)) and not _hits(t, ["iddia", "ittiham", "şikayət"])
    for code, (label, kws) in RISK_CRITERIA.items():
        h = _hits(t, kws)
        if code == "R5" and not _hits(t, ["ittiham", "rüşvət", "korrupsiya", "qanunsuz", "istefa"]):
            h = []
        if code in ("R2", "R4") and interdiction:
            h = []
        if h:
            criteria.append(code)
            reasons.append(f"{code} {label}: '{h[0]}'")
    if mentions >= 3:
        criteria.append("R6")
        reasons.append(f"R6 Geniş yayılma: {mentions} mənbə")
    elif reach.startswith("viral"):
        criteria.append("R6")
        reasons.append(f"R6 Sosial şəbəkədə viral yayılma ({reach[6:].strip()[:80]})")
    fc = fact_check(f"{title}. {body[:400]}", evidence) if evidence.strip() else {"status": "unverified", "evidence_ids": []}
    verified = fc["status"] == "confirmed"
    if fc["status"] == "contradicted":
        reasons.append("Rəsmi mənbə iddianı təkzib edir")

    severe = {"R1", "R2", "R4", "R5"} & set(criteria)
    if content_type == "official" and not severe:
        level, score = "low", 0.1
    elif severe:
        level, score = "high", min(1.0, 0.7 + 0.08 * len(criteria))
    elif criteria:
        level, score = "medium", 0.45 + 0.05 * len(criteria)
    else:
        level, score = "low", 0.2 if sentiment_label == "negative" else 0.05
    review = level == "high" or (level == "medium" and not verified)
    conf = 0.8 if criteria else 0.7
    return {"risk_level": level, "score": round(score, 3), "criteria": criteria, "reasons": reasons,
            "evidence_ids": fc.get("evidence_ids", []), "claim_verified": verified,
            "requires_human_review": review, "confidence": conf}


def rag_answer(question: str, context: str) -> dict[str, Any]:
    blocks = parse_context(context)
    qs = stems(question)
    cands: list[tuple[float, str, str, str]] = []
    for b in blocks:
        for sent in re.split(r"(?<=[.!?])\s+", b["text"]):
            ov = len(qs & stems(sent)) / max(1, len(qs))
            if ov > 0:
                cands.append((ov, sent.strip(), b["id"], b.get("doc_type", "")))
    cands.sort(key=lambda x: -x[0])
    if not cands or cands[0][0] < 0.2:
        return {"answer": "Mövcud təsdiqlənmiş mənbələrdə bu suala cavab vermək üçün kifayət qədər məlumat tapılmadı.",
                "citations": [], "insufficient_evidence": True, "confidence": 0.8}
    used, lines, seen = [], [], set()
    for ov, sent, sid, dtype in cands[:6]:
        if sent in seen or len(lines) >= 3:
            continue
        seen.add(sent)
        prefix = "Rəsmi mənbəyə görə: " if dtype.startswith(("official", "legislation")) else (
            "Media/ictimai rəydə: " if dtype in ("media", "monitoring") else "")
        lines.append(f"{prefix}{sent} [{sid}]")
        if sid not in used:
            used.append(sid)
    conf = round(min(0.9, 0.4 + cands[0][0]), 3)
    return {"answer": " ".join(lines), "citations": used, "insufficient_evidence": False, "confidence": conf}


def executive_summary(period: str, stats: str, items: str) -> dict[str, Any]:
    rows = []
    for line in items.splitlines():
        m = re.match(r"\[(N\d+)\]\s*\(([^)]*)\)\s*(.*)", line.strip())
        if m:
            meta = dict(kv.split("=", 1) for kv in m.group(2).split("; ") if "=" in kv)
            rows.append({"id": m.group(1), "title": m.group(3), **meta})
    if not rows:
        return {"headline": f"{period}: DGK ilə bağlı təsdiqlənmiş xəbər tapılmadı.", "key_points": [], "risks": [],
                "data_gaps": ["Seçilmiş dövrdə məlumat yoxdur"]}
    by_type: dict[str, list[dict]] = {}
    for r in rows:
        by_type.setdefault(r.get("type", "media"), []).append(r)
    names = {"official": "Rəsmi xəbərlər", "media": "Media materialları", "public_opinion": "İctimai rəy və şikayətlər"}
    headline = f"{period}: {len(rows)} DGK xəbəri — " + ", ".join(
        f"{normalize_az(names.get(k, k))}: {len(v)}" for k, v in by_type.items())
    points = []
    for k in ("official", "media", "public_opinion"):
        v = by_type.get(k, [])
        if v:
            top = v[:3]
            points.append({"text": f"{names[k]} ({len(v)}): " + "; ".join(x["title"] for x in top),
                           "citations": [x["id"] for x in top]})
    risks = [{"text": f"{r['title']} — risk: {r.get('risk')}" + (" (təsdiqlənməyib)" if r.get("verified") != "true" else ""),
              "citations": [r["id"]]} for r in rows if r.get("risk") in ("high", "medium")][:5]
    gaps = [f"{names[k]} üzrə məlumat yoxdur" for k in names if k not in by_type]
    return {"headline": headline, "key_points": points, "risks": risks, "data_gaps": gaps}


# ------------------------------------------------------------------ agent
def parse_period(q: str, today: date) -> tuple[str, str, str]:
    t = normalize_az(q)
    if "bu gün" in t or "bugün" in t or "gündəlik" in t:
        d = 1
    elif "dünən" in t:
        d = 2
    elif re.search(r"son (7|yeddi) gün|bu həftə|son həftə|həftəlik", t):
        d = 7
    elif re.search(r"son (bir )?ay|son 30 gün|bu ay", t):
        d = 30
    elif m := re.search(r"son (\d+) gün", t):
        d = int(m.group(1))
    else:
        d = 30
    start = today - timedelta(days=d - 1)
    return start.isoformat(), today.isoformat(), f"{start.isoformat()} — {today.isoformat()}"


def _topic(q: str) -> str:
    drop = {"dgk", "xəbər", "xəbərlər", "xəbərləri", "yayımlanıb", "haqqında", "göstər", "hansı", "hansılardır",
            "son", "gün", "gündə", "bu", "rəsmi", "mənbədə", "təsdiqlənib", "iddia", "mənfi", "rəylər", "mövzularla",
            "bağlıdır", "əsas", "ictimai", "narazılıqlar", "fəaliyyətinə", "dair", "bir", "ayda", "üçün",
            "rəhbərliyi", "gündəlik", "analitik", "icmal", "hazırla", "əvvəl", "məlumat", "bunlardan", "onlardan",
            "hansıları", "nədir", "olub", "olunub", "edilib", "edib", "şikayətləri", "şikayətlər",
            "müxtəlif", "mənbələrdə", "mənbələr", "müqayisə", "et", "xəbərlərini", "xəbərləri", "necə", "təqdim",
            "edilir", "olunur", "statistika", "neçə", "trend", "dinamika", "yüksək", "riskli", "risk"}
    return " ".join(t for t in tokens(q) if t not in drop and not t.isdigit())


def plan_tools(question: str, history: list[tuple[str, str]], tool_names: set[str], today: date) -> list[dict[str, Any]]:
    """Sualın niyyətinə görə alət çağırışlarını planlaşdırır. history: [(rol, mətn)]."""
    t = normalize_az(question)
    date_from, date_to, _ = parse_period(question, today)
    loc = find_location(t)
    topic = _topic(question)
    followup = bool(re.search(r"\b(bunlar|onlar|həmin|bu məlumat|bu xəbər|bu iddia|onlardan|bunlardan)", t))
    prev_human = next((c for r, c in reversed(history) if r == "human"), None)
    prev_ai = next((c for r, c in reversed(history) if r == "ai"), None)
    if followup and prev_human:
        if not loc:
            loc = find_location(prev_human)
        if not re.search(r"son|bu gün|dünən|ay|həftə", t):
            date_from, date_to, _ = parse_period(prev_human, today)
        if not topic:
            topic = _topic(prev_human)
    focus_title = None
    if followup and prev_ai and (m := re.search(r"•\s*(.+?)\s+—", prev_ai)):
        focus_title = m.group(1)

    calls: list[dict[str, Any]] = []
    base = {"date_from": date_from, "date_to": date_to}
    if loc:
        base["location"] = loc
    if re.search(r"hesabat|icmal|brifinq", t):
        calls.append({"name": "generate_report", "args": {"date_from": date_from, "date_to": date_to}})
    elif re.search(r"təsdiqlən|rəsmi mənbə|doğrudur|həqiqətdir|iddia", t):
        claim = focus_title or question
        calls.append({"name": "search_official_sources", "args": {"query": claim, "claim": claim}})
    elif re.search(r"əvvəl(lər)? də|əvvəllər|oxşar|təkrar(lanıb)?|bənzər", t):
        q = focus_title or topic or question
        calls.append({"name": "semantic_search", "args": {"query": q, "k": 5}})
    elif re.search(r"müqayisə|fərqli mənbə|necə təqdim", t):
        calls.append({"name": "compare_news", "args": {"query": focus_title or topic or question, **{k: v for k, v in base.items() if k != "location"}}})
    elif re.search(r"\brisk", t):
        calls.append({"name": "search_news", "args": {**base, "min_risk": "medium", "limit": 10}})
    elif re.search(r"mənfi|müsbət|tonallıq|narazılıq|rəylər|mövzularla", t):
        sent = "positive" if "müsbət" in t else "negative"
        calls.append({"name": "get_trends", "args": {**base, "group_by": "category", "sentiment": sent}})
        calls.append({"name": "search_news", "args": {**base, "sentiment": sent, "limit": 8}})
    elif re.search(r"trend|statistika|neçə|dinamika|say", t):
        calls.append({"name": "get_trends", "args": {**base, "group_by": "day"}})
    else:
        args = {**base, "limit": 10}
        if topic and not loc:
            args["query"] = topic
        if re.search(r"şikayət", t):
            args["content_type"] = "public_opinion"
        calls.append({"name": "search_news", "args": args})
    return [c for c in calls if c["name"] in tool_names]


_CT = {"official": "rəsmi", "media": "media", "public_opinion": "ictimai rəy"}
_SENT = {"positive": "müsbət", "neutral": "neytral", "negative": "mənfi"}
_CAT = {
    "customs_operations": "gömrük əməliyyatları", "smuggling": "qaçaqmalçılıq", "legislation": "qanunvericilik",
    "digital_services": "rəqəmsal xidmətlər", "service_quality": "xidmət keyfiyyəti",
    "corruption_allegation": "korrupsiya iddiası", "revenue_statistics": "gəlir/statistika",
    "international": "beynəlxalq", "management": "rəhbərlik", "other": "digər",
}


def compose_answer(question: str, results: list[dict[str, Any]]) -> str:
    """Alət nəticələrindən mənbəli cavab qurur. Alət nəticəsində olmayan heç nə əlavə edilmir."""
    out: list[str] = []
    period, verified_any = None, None
    for r in results:
        if r.get("error"):
            out.append(f"⚠ {r['tool']}: {r['error']}")
            continue
        period = r.get("period") or period
        if "trends" in r:
            tr = r["trends"]
            if tr:
                out.append("Statistika: " + ", ".join(f"{_CAT.get(k, _SENT.get(k, k))} — {v}" for k, v in tr.items()))
        if "verification" in r:
            v = r["verification"]
            st = {"confirmed": "rəsmi mənbədə TƏSDİQLƏNİB", "contradicted": "rəsmi mənbə TƏKZİB EDİR",
                  "unverified": "rəsmi mənbədə təsdiqlənməyib"}[v["status"]]
            cites = " ".join(f"[{e}]" for e in v.get("evidence_ids", []))
            out.append(f"Yoxlama nəticəsi: {st}. {v.get('explanation', '')} {cites}".strip())
            verified_any = v["status"]
        if "answer" in r:
            out.append(r["answer"])
        if "comparison" in r:
            for g in r["comparison"]:
                out.append(f"• {g['source']} ({_CT.get(g['content_type'], g['content_type'])}, {_SENT.get(g['sentiment'] or '', '—')}): "
                           f"{g['title']} [{g['ref']}]")
        if "report" in r:
            rep = r["report"]
            out.append(f"**{rep['title']}** (status: {rep['status']}, hesabat #{rep['id']})\n{rep['body']}")
        items = r.get("items")
        if items is not None:
            if not items:
                out.append("Göstərilən meyarlara uyğun xəbər tapılmadı.")
            for it in items:
                extra = []
                if it.get("content_type"):
                    extra.append(_CT.get(it["content_type"], it["content_type"]))
                if it.get("sentiment"):
                    extra.append(_SENT.get(it["sentiment"], it["sentiment"]))
                if it.get("risk_level") and it["risk_level"] != "low":
                    extra.append(f"risk: {it['risk_level']}" + (" (insan təsdiqi gözlənilir)" if it.get("risk_status") == "pending_review" else ""))
                if it.get("score") is not None and "ref" in it and it["ref"].startswith("S"):
                    extra.append(f"oxşarlıq {it['score']:.2f}")
                out.append(f"• {it['title']} — {it.get('source', '')}, {str(it.get('date', ''))[:10]} "
                           f"({'; '.join(extra)}) [{it['ref']}]")
    if not out:
        out.append("Bu sual üçün uyğun məlumat tapılmadı.")
    footer = []
    if period:
        footer.append(f"Vaxt aralığı: {period}")
    if verified_any:
        footer.append("Təsdiq statusu: " + {"confirmed": "rəsmi təsdiqlənib", "contradicted": "rəsmi təkzib",
                                             "unverified": "təsdiqlənməyib"}[verified_any])
    else:
        footer.append("Təsdiq statusu: rəsmi (DGK) mənbələr ayrıca işarələnib; media və ictimai rəy materialları təsdiqlənmiş fakt deyil")
    return "\n".join(out) + "\n\n_" + " · ".join(footer) + "_"
