"""Multimodal: şəkil OCR (Tesseract: aze+rus+tur+eng), video transkriptində DGK ifadələri, təhlükəsiz media yükləmə.

- Şəkildəki şəxslərin kimliyi MÜƏYYƏN EDİLMİR (üz tanıma yoxdur).
- Media yalnız icazəli CDN hostlarından, yalnız https, ölçü limiti ilə, şəxsi/daxili IP-lərə qarşı yoxlama ilə yüklənir (SSRF).
- Lokal speech-to-text və Vision modeli bu mərhələdə qoşulmayıb: transkript yalnız platforma onu verdikdə analiz olunur.
"""
from __future__ import annotations

import io
import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from app.intel.lexicon import match

MAX_BYTES = 8 * 1024 * 1024


class MediaFetchError(RuntimeError):
    pass


def ocr_available() -> bool:
    try:
        import pytesseract
        return "aze" in pytesseract.get_languages(config="")
    except Exception:
        return False


def ocr_image(data: bytes, langs: str = "aze+rus+tur+eng") -> str:
    from PIL import Image
    import pytesseract
    img = Image.open(io.BytesIO(data))
    if img.width * img.height > 40_000_000:
        raise MediaFetchError("şəkil çox böyükdür")
    img = img.convert("L")
    if img.width < 1200:  # kiçik şəkillərdə OCR keyfiyyəti üçün böyüt
        img = img.resize((img.width * 2, img.height * 2))
    return " ".join(pytesseract.image_to_string(img, lang=langs, timeout=30).split())


def find_in_transcript(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transkriptin hər seqmentində DGK siqnallarını axtarır və vaxt nişanı ilə qaytarır."""
    out = []
    for seg in segments:
        text = str(seg.get("text", ""))
        if len(text) < 5:
            continue
        m = match(text, "", "social")
        if m.decision != "REJECT":
            out.append({"t": float(seg.get("t", 0)), "text": text[:300], "decision": m.decision,
                        "keywords": m.matched_keywords, "entities": m.matched_entities})
    return out


def _is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def safe_fetch(url: str, allowed_hosts: set[str], timeout: float = 15.0) -> bytes:
    """SSRF-dən qorunan yükləmə: yalnız https, yalnız icazəli hostlar, yönləndirmə yox, ölçü limiti, yalnız image/video."""
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname:
        raise MediaFetchError("yalnız https ünvanlarına icazə var")
    host = u.hostname.lower()
    if not any(host == h or host.endswith("." + h) for h in allowed_hosts):
        raise MediaFetchError(f"host icazəli siyahıda deyil: {host}")
    try:
        ipaddress.ip_address(host)
        raise MediaFetchError("IP ünvanı ilə müraciət qadağandır")
    except ValueError:
        pass
    if not _is_public_host(host):
        raise MediaFetchError("host şəxsi/daxili ünvana yönəlir")
    with httpx.Client(timeout=timeout, follow_redirects=False) as c, c.stream("GET", url) as r:
        if r.status_code != 200:
            raise MediaFetchError(f"HTTP {r.status_code}")
        ctype = r.headers.get("content-type", "")
        if not ctype.startswith(("image/", "video/")):
            raise MediaFetchError(f"gözlənilməz məzmun növü: {ctype}")
        buf = bytearray()
        for chunk in r.iter_bytes():
            buf += chunk
            if len(buf) > MAX_BYTES:
                raise MediaFetchError("fayl ölçü limitini aşır")
    return bytes(buf)
