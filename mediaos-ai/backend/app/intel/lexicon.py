"""DGK Smart Keyword Intelligence — idarə olunan lüğət və üç səviyyəli uyğunluq.

Səviyyələr:
  L1  STRONG      — qurumun adı, rəsmi domen, rəsmi xidmət adı (customs.gov.az, Smart Customs) və DGK struktur bölmələrinin tam adı
  L2  CONTEXTUAL  — gömrük institutu terminləri (gömrük postu, gömrük nəzarəti...), məntəqə + gömrük konteksti,
                    rəhbər adı + DGK konteksti
  L3  WEAK        — idxal, ixrac, ƏDV, tarif, sərhəd... Tək başına HEÇ VAXT DGK-ya aid etmir
  EX              — başqa ölkənin gömrük orqanları və mövzu istisnaları

Qərar: bal 0–100. PUBLISH ≥ 60, REVIEW 35–59, REJECT < 35. Yekun qərarı LLM/semantik yoxlama ilə birlikdə zəncir verir.
Lüğət bazadan (keywords, checkpoints, org_units, persons, positions) oxunur və Redis-də keşlənir; baza əlçatmaz
olarsa daxili lüğət + data/dgk_registry.json istifadə olunur.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.text import normalize_az

REGISTRY = Path(__file__).resolve().parents[2] / "data" / "dgk_registry.json"

# ------------------------------------------------------------------ transliterasiya
_FOLD = str.maketrans({"ə": "e", "ö": "o", "ü": "u", "ğ": "g", "ı": "i", "ş": "s", "ç": "c"})
_EN = [("ə", "a"), ("ş", "sh"), ("ç", "ch"), ("ğ", "gh"), ("ı", "i"), ("ö", "o"), ("ü", "u"), ("x", "kh"),
       ("q", "g"), ("c", "j"), ("Ə", "A"), ("Ş", "Sh"), ("Ç", "Ch"), ("Ğ", "Gh"), ("I", "I"), ("Ö", "O"), ("Ü", "U"),
       ("X", "Kh"), ("Q", "G"), ("C", "J")]
_TR = [("ə", "e"), ("x", "h"), ("q", "k"), ("Ə", "E"), ("X", "H"), ("Q", "K")]
_RU = {"a": "а", "b": "б", "c": "дж", "ç": "ч", "d": "д", "e": "е", "ə": "а", "f": "ф", "g": "г", "ğ": "г", "h": "г",
       "x": "х", "ı": "ы", "i": "и", "j": "ж", "k": "к", "q": "г", "l": "л", "m": "м", "n": "н", "o": "о", "ö": "ё",
       "p": "п", "r": "р", "s": "с", "ş": "ш", "t": "т", "u": "у", "ü": "ю", "v": "в", "y": "й", "z": "з"}


def fold(s: str) -> str:
    return s.translate(_FOLD)


def to_en(s: str) -> str:
    for a, b in _EN:
        s = s.replace(a, b)
    return s


def to_tr(s: str) -> str:
    for a, b in _TR:
        s = s.replace(a, b)
    return s


def to_ru(s: str) -> str:
    out = []
    for ch in s:
        low = ch.lower()
        r = _RU.get(low, ch)
        out.append(r.capitalize() if ch.isupper() and r else r)
    return "".join(out)


def name_variants(given: str, surname: str) -> dict[str, list[str]]:
    """Avtomatik ad variantları. RU/EN/TR transliterasiyası təxminidir və 'auto' kimi işarələnir."""
    az = [f"{given} {surname}", f"{surname} {given}", f"{given[0]}. {surname}"]
    return {"az": az, "ascii": sorted({fold(x.lower()) for x in az}), "en": [to_en(x) for x in az[:2]],
            "tr": [to_tr(x) for x in az[:2]], "ru": [to_ru(x) for x in az[:2]], "auto": True}


# ------------------------------------------------------------------ daxili lüğət
BUILTIN: list[tuple[str, str, str, str]] = [
    # (term, level, category, lang)
    ("Dövlət Gömrük Komitəsi", "L1", "institution", "az"), ("Azərbaycan Respublikası Dövlət Gömrük Komitəsi", "L1", "institution", "az"),
    ("Azərbaycan Dövlət Gömrük Komitəsi", "L1", "institution", "az"), ("DGK", "L1", "institution", "az"),
    ("Gömrük Komitəsi", "L1", "institution", "az"), ("Azərbaycan gömrüyü", "L1", "institution", "az"),
    ("Azərbaycan gömrük", "L1", "institution", "az"),
    ("customs.gov.az", "L1", "digital", "xx"), ("e.customs.gov.az", "L1", "digital", "xx"), ("Smart Customs", "L1", "digital", "en"),
    ("e-gömrük", "L1", "digital", "az"), ("e-customs", "L1", "digital", "en"),
    ("Государственный таможенный комитет", "L1", "institution", "ru"), ("ГТК Азербайджана", "L1", "institution", "ru"),
    ("таможня Азербайджана", "L1", "institution", "ru"), ("азербайджанская таможня", "L1", "institution", "ru"),
    ("State Customs Committee", "L1", "institution", "en"), ("SCC Azerbaijan", "L1", "institution", "en"),
    ("Azerbaijan customs", "L1", "institution", "en"), ("Azerbaijani customs", "L1", "institution", "en"),
    ("Devlet Gümrük Komitesi", "L1", "institution", "tr"), ("Azerbaycan gümrüğü", "L1", "institution", "tr"),
    # L2 — gömrük institutu
    ("gömrük xidməti", "L2", "structure", "az"), ("gömrük orqanları", "L2", "structure", "az"),
    ("gömrük idarəsi", "L2", "structure", "az"), ("gömrük postu", "L2", "structure", "az"),
    ("gömrük əməkdaşı", "L2", "structure", "az"), ("gömrük inspektoru", "L2", "structure", "az"),
    ("gömrük nəzarəti", "L2", "operation", "az"), ("gömrük rəsmiləşdirilməsi", "L2", "operation", "az"),
    ("gömrük yoxlaması", "L2", "operation", "az"), ("gömrük proseduru", "L2", "operation", "az"),
    ("gömrük bəyannaməsi", "L2", "operation", "az"), ("gömrük terminalı", "L2", "structure", "az"),
    ("gömrük rüsumu", "L2", "operation", "az"), ("gömrük ödənişləri", "L2", "operation", "az"),
    ("gömrük dəyəri", "L2", "operation", "az"), ("gömrük tarifi", "L2", "operation", "az"),
    ("sərhəd-keçid məntəqəsi", "L2", "structure", "az"), ("elektron gömrük", "L2", "digital", "az"),
    ("elektron bəyannamə", "L2", "digital", "az"), ("bəyan edilməmiş mal", "L2", "violation", "az"),
    ("gömrük qaydalarının pozulması", "L2", "violation", "az"), ("gömrük nəzarətindən gizlədil", "L2", "violation", "az"),
    ("gömrük ərazisi", "L2", "structure", "az"), ("gömrük keçid", "L2", "structure", "az"),
    ("таможенный пост", "L2", "structure", "ru"), ("таможенный контроль", "L2", "operation", "ru"),
    ("таможенное оформление", "L2", "operation", "ru"), ("таможенная пошлина", "L2", "operation", "ru"),
    ("таможенник", "L2", "structure", "ru"), ("таможенная декларация", "L2", "operation", "ru"),
    ("customs post", "L2", "structure", "en"), ("customs clearance", "L2", "operation", "en"),
    ("customs officer", "L2", "structure", "en"), ("customs duty", "L2", "operation", "en"),
    ("customs declaration", "L2", "operation", "en"),
    # L3 — zəif, ümumi terminlər
    ("gömrük", "L3", "generic", "az"), ("gömrükçü", "L3", "generic", "az"), ("idxal", "L3", "trade", "az"),
    ("ixrac", "L3", "trade", "az"), ("tranzit", "L3", "trade", "az"), ("reeksport", "L3", "trade", "az"),
    ("yük daşıma", "L3", "trade", "az"), ("aksiz", "L3", "trade", "az"), ("ƏDV", "L3", "trade", "az"),
    ("tarif", "L3", "trade", "az"), ("sərhəd", "L3", "trade", "az"), ("qaçaqmal", "L3", "violation", "az"),
    ("bəyannamə", "L3", "operation", "az"), ("rüsum", "L3", "trade", "az"), ("elektron növbə", "L3", "digital", "az"),
    ("e-növbə", "L3", "digital", "az"), ("таможн", "L3", "generic", "ru"), ("контрабанд", "L3", "violation", "ru"),
    ("customs", "L3", "generic", "en"), ("smuggling", "L3", "violation", "en"), ("gümrük", "L3", "generic", "tr"),
    # EX — xarici gömrük orqanları və mövzu istisnaları
    ("Federal Gömrük Xidməti", "EX", "foreign", "az"), ("ФТС", "EX", "foreign", "ru"), ("Федеральная таможенная служба", "EX", "foreign", "ru"),
    ("U.S. Customs", "EX", "foreign", "en"), ("CBP", "EX", "foreign", "en"), ("HMRC", "EX", "foreign", "en"),
    ("Kapıkule", "EX", "foreign", "tr"), ("Sarpi", "EX", "foreign", "az"), ("Xorqos", "EX", "foreign", "az"),
    ("Верхний Ларс", "EX", "foreign", "ru"), ("Ticaret Bakanlığı", "EX", "foreign", "tr"),
    ("gömrük ittifaqı", "EX", "noise", "az"), ("Таможенный союз", "EX", "noise", "ru"), ("futbol", "EX", "noise", "az"),
    ("voleybol", "EX", "noise", "az"), ("basketbol", "EX", "noise", "az"), ("hava proqnozu", "EX", "noise", "az"),
    ("konsert", "EX", "noise", "az"), ("serial", "EX", "noise", "az"), ("tamaşa", "EX", "noise", "az"),
]

FOREIGN_RE = re.compile(
    r"(gürcüstan|rusiya|türkiyə|türkiye|iran|qazaxıstan|özbəkistan|avropa|abş|çin|ukrayna|almaniya|fransa|"
    r"georgia|russia|turkey|türkiye|kazakhstan|uzbekistan|china|ukraine|грузи|росси|турци|казахстан|узбекистан|"
    r"gürcistan|rusya|kazakistan)\w*\s+(\w+\s+)?(gömrü|gümrü|customs|таможн|gəlirlər|federal)"
)
AZ_CONTEXT_RE = re.compile(r"azərbaycan|azerbaycan|azerbaijan|азербайджан|\bdgk\b|dövlət gömrük komitə")
CUSTOMS_CTX_RE = re.compile(r"gömrü|gomru|таможн|customs|gümrü|sərhəd-keçid|keçid məntəqə")
PROCESS_CTX_RE = re.compile(
    r"keçid|kecid|sərhəd|serhed|yük maşın|yuk masin|fura|tır\b|tir\b|sənəd\w* yoxla|yoxlan\w*|bəyan|rəsmiləşdir|"
    r"очеред|граница|пункт пропуска|фур|border crossing|checkpoint|trucks?")
OTHER_AGENCY_RE = re.compile(r"sərhədçi|dövlət sərhəd xidməti|\bdsx\b|pasport nəzarət|viza|пограничн|border guard")
TITLE_RE = re.compile(r"sədr|rəis|müavin|aparat rəhbəri|председател|начальник|chairman|head of|deputy")


def _stem_last(term: str) -> str:
    """Çoxsözlü terminin son sözündən mənsubiyyət şəkilçisini çıxarır:
    'gömrük rüsumu' → 'gömrük rüsum' (rüsumları, rüsumlarının da tutulsun)."""
    words = term.split()
    if len(words) < 2 or not re.search(r"[a-zəğıöşüç]", words[-1]):
        return term
    last = re.sub(r"(s?[ıiuü])$", "", words[-1])
    return " ".join(words[:-1] + [last]) if len(last) >= 3 else term


def _pattern(term: str) -> re.Pattern:
    """Söz sərhədi ilə, son sözə Azərbaycan şəkilçisi icazəsi ilə (gömrük postu → gömrük postunda)."""
    base = _stem_last(normalize_az(term))
    t = re.escape(base).replace(r"\ ", r"\s+")
    # Samit əvəzlənməsi: gömrük → gömrüyü, gömrüğün; qaçaq → qaçağı
    if re.search(r"[a-zəğıöşüç]k$", base):
        t = t[:-1] + "[kyğ]"
    elif re.search(r"[a-zəğıöşüç]q$", base):
        t = t[:-1] + "[qğ]"
    return re.compile(rf"(?<![\w]){t}\w*" if len(term) > 3 else rf"(?<![\w]){t}(?![\w])")


@dataclass
class Term:
    term: str
    level: str
    category: str
    lang: str
    pats: list[re.Pattern]
    keyword_id: int | None = None


@dataclass
class Entity:
    kind: str  # unit | checkpoint | person
    id: int | str
    name: str
    pats: list[re.Pattern]
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Lexicon:
    terms: list[Term]
    entities: list[Entity]
    version: str = "builtin"


def _mk_term(term: str, level: str, cat: str, lang: str, variants: list[str] | None = None, kid: int | None = None) -> Term:
    forms = {term, *(variants or [])}
    pats = []
    for f in forms:
        pats.append(_pattern(f))
        ff = fold(normalize_az(f))
        if ff != normalize_az(f):
            pats.append(_pattern(ff))
    return Term(term, level, cat, lang, pats, kid)


def _mk_entity(kind: str, eid: Any, name: str, forms: list[str], meta: dict[str, Any] | None = None) -> Entity:
    pats = []
    allf = set()
    for f in {name, *forms}:
        allf.add(f)
        # Rus dilində hal şəkilçiləri son saiti dəyişir: Астара → в Астаре / Астары
        if re.search(r"[а-яё]", f.lower()) and f.lower()[-1] in "аяоеиы" and len(f) > 5:
            allf.add(f[:-1])
    for f in allf:
        if len(f) < 3:
            continue
        pats.append(_pattern(f))
        ff = fold(normalize_az(f))
        if ff != normalize_az(f):
            pats.append(_pattern(ff))
    return Entity(kind, eid, name, pats, meta or {})


def _unit_forms(name: str) -> list[str]:
    # "Bakı Baş Gömrük İdarəsi" → həmçinin "Bakı BGİ"
    forms = [name]
    if "Baş Gömrük İdarəsi" in name:
        forms.append(name.replace("Baş Gömrük İdarəsi", "BGİ"))
    return forms


def _parse_dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc) if s else None


def build_from_registry() -> Lexicon:
    terms = [_mk_term(t, lv, c, lg) for t, lv, c, lg in BUILTIN]
    ents: list[Entity] = []
    if REGISTRY.exists():
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for u in reg["units"]:
            if u["kind"] != "leadership":
                ents.append(_mk_entity("unit", u["slug"], u["name"], _unit_forms(u["name"]), {"slug": u["slug"]}))
        for c in reg["checkpoints"]:
            ents.append(_mk_entity("checkpoint", c["name"], c["name"], c.get("variants", []), {"unit": c.get("unit")}))
        for p in reg["people"]:
            surname, given = p["name"].split()[:2]
            v = name_variants(given, surname)
            forms = v["az"] + v["ascii"] + v["en"] + v["tr"] + v["ru"]
            ents.append(_mk_entity("person", p["name"], p["name"], forms, {"positions": [
                {"id": None, "unit": x["unit"], "title": x["title"], "status": x["status"],
                 "start": _parse_dt(x.get("start")), "end": _parse_dt(x.get("end"))} for x in p["positions"]]}))
    return Lexicon(terms, ents, "registry-file")


def build_from_db() -> Lexicon:
    from sqlalchemy import select
    from app.db import session_scope
    from app.models import Checkpoint, Keyword, OrgUnit, Person, Position
    with session_scope() as db:
        kws = db.scalars(select(Keyword).where(Keyword.active.is_(True))).all()
        if not kws:
            raise LookupError("keywords cədvəli boşdur")
        terms = [_mk_term(k.term, k.level, k.category, k.lang, k.variants, k.id) for k in kws]
        ents: list[Entity] = []
        units = {u.id: u for u in db.scalars(select(OrgUnit).where(OrgUnit.active.is_(True)))}
        for u in units.values():
            if u.kind != "leadership":
                ents.append(_mk_entity("unit", u.id, u.name, _unit_forms(u.name) + list(u.variants.get("forms", [])),
                                       {"slug": u.slug}))
        for c in db.scalars(select(Checkpoint).where(Checkpoint.active.is_(True))):
            ents.append(_mk_entity("checkpoint", c.id, c.name, list(c.variants or []), {"unit_id": c.unit_id}))
        positions: dict[int, list[dict[str, Any]]] = {}
        for p in db.scalars(select(Position)):
            positions.setdefault(p.person_id, []).append({"id": p.id, "unit": p.unit_id, "title": p.title, "status": p.status,
                                                          "start": p.start_date, "end": p.end_date})
        for p in db.scalars(select(Person)):
            v = p.variants or {}
            forms = [*v.get("az", []), *v.get("ascii", []), *v.get("en", []), *v.get("tr", []), *v.get("ru", [])]
            ents.append(_mk_entity("person", p.id, p.full_name, forms, {"positions": positions.get(p.id, [])}))
    return Lexicon(terms, ents, f"db@{int(time.time())}")


_lex: Lexicon | None = None
_lex_at = 0.0
_lock = threading.Lock()


def get_lexicon(max_age_s: float = 60.0) -> Lexicon:
    """Proses daxilində 60 s keşlənir; admin dəyişikliyi `invalidate()` ilə dərhal tətbiq olunur."""
    global _lex, _lex_at
    with _lock:
        if _lex is not None and time.monotonic() - _lex_at < max_age_s:
            return _lex
        try:
            _lex = build_from_db()
        except Exception:
            _lex = build_from_registry()
        _lex_at = time.monotonic()
        return _lex


def invalidate() -> None:
    global _lex
    with _lock:
        _lex = None
    try:
        from app.cache.redis_cache import get_cache
        get_cache().invalidate("lexicon")
    except Exception:
        pass


# ------------------------------------------------------------------ uyğunluq
def detect_language(text: str) -> str:
    if not text:
        return "unknown"
    cyr = sum("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in text)
    if cyr > len(text) * 0.3:
        return "ru"
    t = text.lower()
    if "ə" in t:
        return "az"
    if re.search(r"\b(ve|için|bir|ile|gümrük|olarak)\b", t):
        return "tr"
    if re.search(r"\b(the|and|of|is|has|with)\b", t):
        return "en"
    return "az" if re.search(r"[ğışçöü]", t) else "unknown"


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?…])\s+|\n+", text) if s.strip()]


def _hits(pats: list[re.Pattern], text: str, ftext: str) -> str | None:
    for p in pats:
        m = p.search(text) or p.search(ftext)
        if m:
            return m.group(0)
    return None


@dataclass
class MatchResult:
    score: int
    level: str  # DIRECT | CONTEXTUAL | WEAK | NONE
    decision: str  # PUBLISH | REVIEW | REJECT
    matched_keywords: list[str]
    matched_entities: list[str]
    evidence: list[str]
    reasons: list[str]
    foreign: bool
    noise: bool
    persons: list[dict[str, Any]]
    checkpoints: list[dict[str, Any]]
    units: list[dict[str, Any]]
    keyword_ids: list[int]
    language: str
    responsibility: str  # DGK | other_agency_possible | unknown

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _position_at(positions: list[dict[str, Any]], when: datetime | None) -> dict[str, Any] | None:
    if not positions:
        return None
    when = when or datetime.now(timezone.utc)
    ok = [p for p in positions if (p["start"] is None or p["start"] <= when) and (p["end"] is None or p["end"] > when)]
    if not ok:
        return None
    # tarixi dəqiq olan, daha sonra başlayan vəzifə üstündür
    ok.sort(key=lambda p: (p["start"] is not None, p["start"] or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    return ok[0]


def match(title: str, body: str, source_kind: str = "media", published_at: datetime | None = None,
          lex: Lexicon | None = None) -> MatchResult:
    lex = lex or get_lexicon()
    raw = f"{title}\n{body}"
    nt, nb = normalize_az(title), normalize_az(body)
    full = f"{nt} \n {nb}"
    ffull = fold(full)
    score = 0.0
    kws: list[str] = []
    kw_ids: list[int] = []
    evidence: list[str] = []
    reasons: list[str] = []
    levels: set[str] = set()
    foreign = noise = False
    l3 = 0

    for t in lex.terms:
        hit = _hits(t.pats, full, ffull)
        if not hit:
            continue
        in_title = bool(_hits(t.pats, nt, fold(nt)))
        w = 1.3 if in_title else 1.0
        if t.level == "EX":
            if t.category == "noise":
                noise = True
            else:
                foreign = True
            reasons.append(f"istisna: {t.term}")
            continue
        kws.append(t.term)
        if t.keyword_id:
            kw_ids.append(t.keyword_id)
        levels.add(t.level)
        if t.level == "L1":
            score += (60 if "L1" not in reasons else 15) * w
            reasons.append("L1")
        elif t.level == "L2":
            score += 40 * w if not any(r == "L2" for r in reasons) else 20
            reasons.append("L2")
        else:
            l3 += 1
    score += min(15, 6 * l3)

    customs_ctx = bool(CUSTOMS_CTX_RE.search(full) or CUSTOMS_CTX_RE.search(ffull))
    process_ctx = bool(PROCESS_CTX_RE.search(full) or PROCESS_CTX_RE.search(ffull))
    entities: list[str] = []
    persons, cps, units = [], [], []
    for e in lex.entities:
        hit = _hits(e.pats, full, ffull)
        if not hit:
            continue
        if e.kind == "unit":
            units.append({"id": e.id, "name": e.name})
            entities.append(e.name)
            score += 60
            levels.add("L1")
            evidence.append(f"struktur bölmə: {e.name}")
        elif e.kind == "checkpoint":
            # Yer adı tək başına DGK demək deyil — gömrük və ya keçid prosesi konteksti lazımdır
            sent = next((s for s in _sentences(raw) if _hits(e.pats, normalize_az(s), fold(normalize_az(s)))), "")
            ns = normalize_az(sent)
            if CUSTOMS_CTX_RE.search(ns) or CUSTOMS_CTX_RE.search(fold(ns)):
                cps.append({"id": e.id, "name": e.name, "confirmed": True})
                entities.append(e.name)
                score += 55
                levels.add("L2")
                evidence.append(f"məntəqə + gömrük konteksti: «{sent.strip()[:160]}»")
            elif PROCESS_CTX_RE.search(ns) or PROCESS_CTX_RE.search(fold(ns)):
                cps.append({"id": e.id, "name": e.name, "confirmed": False})
                entities.append(e.name)
                score += 38
                levels.add("SEM")
                evidence.append(f"semantik: məntəqə + keçid/yük prosesi, gömrük sözü yoxdur: «{sent.strip()[:160]}»")
        elif e.kind == "person":
            pos = _position_at(e.meta.get("positions", []), published_at)
            confirmed = bool(levels & {"L1", "L2"}) or customs_ctx and bool(TITLE_RE.search(full))
            persons.append({"id": e.id, "name": e.name, "matched": hit, "confirmed": confirmed,
                            "position": pos and {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in pos.items()}})
            if confirmed:
                entities.append(e.name)
                score += 25
                evidence.append(f"rəhbər adı DGK kontekstində: {hit}" + (f" ({pos['title']})" if pos else " (xəbər tarixində vəzifə məlum deyil)"))
            else:
                reasons.append(f"ad uyğunluğu təsdiqlənmədi (eyniadlı şəxs ola bilər): {hit}")

    az_ctx = bool(AZ_CONTEXT_RE.search(full) or AZ_CONTEXT_RE.search(ffull) or units or any(c["confirmed"] for c in cps))
    if not foreign and (FOREIGN_RE.search(full) or FOREIGN_RE.search(ffull)):
        foreign = True
    if foreign and not az_ctx:
        score -= 70
        reasons.append("başqa ölkənin gömrük orqanı")
    elif foreign:
        reasons.append("xarici gömrük adı çəkilir, amma Azərbaycan/DGK konteksti var")
    if noise and not (levels & {"L1"}):
        score -= 40
    if source_kind == "official" and (levels or l3):
        score += 15
    lang = detect_language(raw)
    if lang == "az" and "L2" in levels and not foreign:
        score += 15
        reasons.append("Azərbaycan dilində gömrük institutu termini, xarici gömrük adı yoxdur")
    responsibility = "unknown"
    if OTHER_AGENCY_RE.search(full) or OTHER_AGENCY_RE.search(ffull):
        responsibility = "other_agency_possible"
        if not (levels & {"L1", "L2"}):
            score -= 15
            reasons.append("sərhəd/pasport nəzarəti başqa qurumun (DSX) səlahiyyəti ola bilər")
    elif levels & {"L1", "L2"}:
        responsibility = "DGK"

    score = int(max(0, min(100, round(score))))
    if foreign and not az_ctx:
        level = "NONE"
    elif levels & {"L1"}:
        level = "DIRECT"
    elif levels & {"L2", "SEM"}:
        level = "CONTEXTUAL"
    elif l3:
        level = "WEAK"
    else:
        level = "NONE"
    if level == "WEAK":
        score = min(score, 30)  # L3 tək başına heç vaxt qəbul etdirmir
    decision = "PUBLISH" if score >= 60 else "REVIEW" if score >= 35 else "REJECT"
    if kws:
        evidence.insert(0, "açar sözlər: " + ", ".join(dict.fromkeys(kws)))
    return MatchResult(score, level, decision, list(dict.fromkeys(kws)), list(dict.fromkeys(entities)), evidence,
                       reasons, foreign, noise, persons, cps, units, kw_ids, lang, responsibility)
