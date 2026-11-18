"""DGK Structure & Management, açar söz idarəetməsi və relevance v2 ssenariləri."""
from datetime import datetime, timezone

import pytest

from app.intel.lexicon import get_lexicon, invalidate, match
from tests.conftest import auth

SCENARIOS = [
    ("DGK rəsmi xəbəri", "Dövlət Gömrük Komitəsində kollegiya iclası keçirilib", "official", "PUBLISH"),
    ("Astara — əlaqəsiz", "Astara rayonunda məktəb əsaslı təmir edildi", "media", "REJECT"),
    ("post, DGK abbr. yoxdur", "Astara gömrük postunda yük avtomobillərinin keçidində gecikmə yaranıb", "media", "PUBLISH"),
    ("semantik, açar söz yoxdur", "Astara keçidində yük maşınlarının sənədlərinin yoxlanılması uzun çəkir.", "social", "REVIEW"),
    ("başqa ölkə", "Qazaxıstan gömrük orqanları Xorqosda yeni terminal açıb", "media", "REJECT"),
    ("türkcə Kapıkule", "Kapıkule gümrük kapısında 5 saatlik bekleyiş var", "social", "REJECT"),
    ("rəhbər + struktur", "Bakı Baş Gömrük İdarəsinin rəisi Elmir Ramazanov sahibkarlarla görüşüb", "media", "PUBLISH"),
    ("eyniadlı şəxs", "Vüqar Əliyev futbol üzrə məşqçi təyin olunub", "media", "REJECT"),
    ("yalnız idxal", "Azərbaycanın idxalı 9 ayda 12 faiz artıb, ixrac isə azalıb", "media", "REJECT"),
    ("rus dili", "Государственный таможенный комитет Азербайджана предотвратил контрабанду", "media", "PUBLISH"),
    ("rus — məntəqə", "На таможне в Астаре образовалась очередь из фур", "social", "PUBLISH"),
    ("ingilis", "The State Customs Committee of Azerbaijan launched a new service", "media", "PUBLISH"),
    ("domen", "Bəyannaməni e.customs.gov.az portalında doldurmaq olar", "social", "PUBLISH"),
    ("zəif + yer: liman", "Bakı limanında tranzit yük dövriyyəsi 15 faiz artıb", "media", "REJECT"),
    ("zəif + yer: polis", "Astara rayon polisi narkotik qaçaqmalçısını saxlayıb", "media", "REJECT"),
    ("zəif + yer: aksiz", "Naxçıvanda aksiz markası olmayan siqaret satan mağaza cərimələnib", "media", "REJECT"),
    ("Gömrükçü klubu", "Gömrükçü voleybol komandası finala yüksəldi", "media", "REJECT"),
    ("pasport — DSX", "Astara keçidində pasport nəzarətində sərhədçilər uzun yoxlama aparır", "social", "REJECT"),
    ("Ağbənd infrastruktur", "Ağbənd gömrük-sərhəd infrastrukturu üzrə tikinti işləri aparılır", "media", "PUBLISH"),
]


@pytest.mark.parametrize("name,text,kind,expected", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_relevance_v2_scenarios(name, text, kind, expected):
    invalidate()
    assert match(text, text, kind).decision == expected


def test_lexicon_loaded_from_db():
    invalidate()
    lex = get_lexicon()
    assert lex.version.startswith("db@") and len(lex.terms) >= 90


def test_old_news_maps_to_position_at_publication_date():
    r = match("Bakı Baş Gömrük İdarəsinin rəisi Elmir Ramazanov", "", "media",
              published_at=datetime(2023, 1, 1, tzinfo=timezone.utc))
    p = next(x for x in r.persons if "Ramazanov" in x["name"])
    assert p["confirmed"] and "müavini" in p["position"]["title"]   # 2023-də rəis müavini idi


def test_structure_endpoint(client):
    s = client.get("/api/structure", headers=auth("viewer")).json()
    names = {u["name"] for u in s["units"]}
    for n in ("Bakı Baş Gömrük İdarəsi", "Naxçıvan Baş Gömrük İdarəsi", "Rəqəmsal İdarəetmə Baş İdarəsi",
              "Gömrük Siyasəti Baş İdarəsi", "Hava Nəqliyyatında Baş Gömrük İdarəsi", "Aksizli Mallar üzrə Baş Gömrük İdarəsi"):
        assert n in names
    lead = next(u for u in s["units"] if u["slug"] == "leadership")
    chair = [x for x in lead["leaders"] if x["title"] == "Komitə sədri"]
    assert chair[0]["status"] == "təsdiqlənmiş" and "Bağırov" in chair[0]["name"]
    assert any(x["status"] == "keçmiş rəhbər" for x in chair)            # keçmiş sədr tarixçədədir
    baki = next(u for u in s["units"] if u["slug"] == "baki")
    assert any("Ramazanov" in x["name"] and x["status"] == "yoxlanmalıdır" for x in baki["leaders"])
    assert set(s["position_status"]) <= {"təsdiqlənmiş", "yoxlanmalıdır", "keçmiş rəhbər"}


def test_person_page_has_no_reputation_score(client):
    s = client.get("/api/structure", headers=auth("viewer")).json()
    pid = next(x["person_id"] for u in s["units"] for x in u["leaders"] if "Bağırov" in x["name"])
    p = client.get(f"/api/persons/{pid}", headers=auth("viewer")).json()
    assert p["positions"] and "reputasiya" in p["note"]
    assert not any(k in p for k in ("score", "reputation", "risk_score"))


def test_keyword_management_and_audit(client):
    assert client.post("/api/keywords", headers=auth("analyst"), json={"term": "x test", "level": "L3", "category": "t"}).status_code == 403
    r = client.post("/api/keywords", headers=auth("admin"),
                    json={"term": "Gömrük Akademiyası", "level": "L1", "category": "institution", "variants": ["Gomruk Akademiyasi"]})
    kid = r.json()["id"]
    invalidate()
    assert match("Gomruk Akademiyasi mezunlari", "", "media").level == "DIRECT"
    assert client.patch(f"/api/keywords/{kid}", headers=auth("admin"), json={"active": False}).status_code == 200
    invalidate()
    assert match("Gomruk Akademiyasi mezunlari", "", "media").level != "DIRECT"
    hist = client.get(f"/api/keywords/{kid}/audit", headers=auth("analyst")).json()
    assert [h["action"] for h in hist] == ["keyword.update", "keyword.create"]
    kws = client.get("/api/keywords", headers=auth("analyst")).json()
    assert any(k["term"] == "Dövlət Gömrük Komitəsi" and k["hits"] > 0 for k in kws)
    t = client.post("/api/keywords/test", headers=auth("analyst"), json={"text": "Astara gömrük postunda növbə"}).json()
    assert t["decision"] == "PUBLISH" and "Astara" in t["matched_entities"]


def test_official_routine_news_has_no_risk(client):
    items = client.get("/api/news/latest?limit=100&content_type=official", headers=auth("viewer")).json()
    routine = [i for i in items if "e-gömrük" in i["title"].lower() or "terminal" in i["title"].lower()]
    assert routine and all(i["risk_level"] == "none" for i in routine)


def test_ocr_reads_customs_text_from_image(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    from app.intel.media import ocr_image
    img = Image.new("RGB", (900, 160), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
    except OSError:
        font = ImageFont.load_default()
    d.text((20, 50), "DÖVLƏT GÖMRÜK KOMİTƏSİ", fill="black", font=font)
    p = tmp_path / "x.png"
    img.save(p)
    text = ocr_image(p.read_bytes())
    assert "GÖMRÜK" in text.upper() or "GOMRUK" in text.upper()
    assert match("Şəkil", f"[Şəkildəki mətn (OCR): {text}]", "social").decision == "PUBLISH"


def test_video_transcript_timestamps():
    from app.intel.media import find_in_transcript
    tr = [{"t": 3.0, "text": "salam dostlar"}, {"t": 41.5, "text": "Astara gömrük postunda 3 saat gözlədik"},
          {"t": 80.0, "text": "sonra yola davam etdik"}]
    hits = find_in_transcript(tr)
    assert [h["t"] for h in hits] == [41.5]


def test_ssrf_guard_blocks_private_and_unlisted_hosts():
    from app.intel.media import MediaFetchError, safe_fetch
    for url in ("http://127.0.0.1/x.png", "https://169.254.169.254/latest", "file:///etc/passwd",
                "https://evil.example.com/a.png"):
        with pytest.raises(MediaFetchError):
            safe_fetch(url, allowed_hosts={"scontent.cdninstagram.com"})
