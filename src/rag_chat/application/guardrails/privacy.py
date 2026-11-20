"""Bounded, deterministic DLP signals; not comprehensive secret or PII detection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import replace
from urllib.parse import urlsplit

from rag_chat.domain.errors import GuardrailRule, GuardrailViolation
from rag_chat.domain.models import SourceDocument

_SECRET = re.compile(
    r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----|"
    r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bsk-[A-Za-z0-9_-]{16,}|"
    r"\b(?:password|passwd|contrase[ñn]a|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|client[_-]?secret|secret[_-]?key|signature|sig)"
    r"\s*[\"']?\s*[:=]\s*[\"']?[^\s\"'&,;]+|"
    r"\bBearer\s+[A-Za-z0-9._~+/-]+=*|https?://[^\s/@]+:[^\s/@]+@",
    re.IGNORECASE,
)
_MASKS = (
    (re.compile(r"\b[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]){11,30}\b", re.I), "[BANK_ACCOUNT]"),
    (
        re.compile(
            r"\b(?:DNI|NIE|NIF|passport|pasaporte|identity|ID)\b\s*[:#=-]?\s*"
            r"(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{5,19}\b",
            re.I,
        ),
        "[IDENTITY]",
    ),
    (re.compile(r"\b(?:\d{8}[A-Z]|[XYZ]\d{7}[A-Z])\b", re.I), "[IDENTITY]"),
    (
        re.compile(
            r"\b(?:bank\s*account|cuenta\s*bancaria)\s*[:#=-]?\s*"
            r"\d(?:[ -]?\d){7,23}\b",
            re.I,
        ),
        "[BANK_ACCOUNT]",
    ),
    (re.compile(r"\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I), "[EMAIL]"),
    (re.compile(r"(?<!\w)\+\d(?:[ ().-]?\d){7,14}(?!\w)"), "[PHONE]"),
    (
        re.compile(
            r"\b(?:phone|tel[eé]fono|tel|mobile|m[oó]vil)\s*[:#=-]?\s*"
            r"\d(?:[ ().-]?\d){6,14}\b",
            re.I,
        ),
        "[PHONE]",
    ),
    (re.compile(r"(?<![\w.-])[6789]\d{8}(?![\w.-])"), "[PHONE]"),
)
_INJECTION = re.compile(
    r"\b(?:ignore|disregard|override)\b.{0,60}\b(?:instructions?|system|rules?|prompt)\b|"
    r"\b(?:ignora|ignore|omitir|omite)\b.{0,60}\b(?:instrucciones|reglas|sistema)\b|"
    r"\b(?:reveal|print|show|revela|muestra)\b.{0,40}\b(?:system prompt|prompt del sistema)\b|"
    r"<\|(?:system|im_start|im_end)\|>",
    re.I | re.S,
)


def protect_text(value: str) -> str:
    """Reject detected secrets before masking recognized personal identifiers."""
    normalized = unicodedata.normalize("NFKC", value)
    if _SECRET.search(normalized):
        raise GuardrailViolation(
            "Detected credentials or secrets; remove them before continuing.",
            rule=GuardrailRule.SECRET,
        )
    for pattern, replacement in _MASKS:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def validate_untrusted(value: str) -> None:
    """Reject explicit override signals; authorization remains an independent boundary."""
    normalized = "".join(
        char for char in unicodedata.normalize("NFKC", value) if unicodedata.category(char) != "Cf"
    )
    if _INJECTION.search(normalized):
        raise GuardrailViolation(
            "The content contains an instruction-override signal. Rephrase the request.",
            rule=GuardrailRule.INJECTION,
        )


def protect_source(source: SourceDocument) -> SourceDocument:
    values = [
        protect_text(value)
        for value in (
            source.document_id,
            source.content,
            source.title,
        )
    ]
    uri = protect_text(source.uri) if source.uri else None
    # Never publish a transformed URL or a non-web scheme as an actionable link.
    if uri and (uri != source.uri or urlsplit(uri).scheme not in {"http", "https"}):
        uri = None
    return replace(
        source,
        document_id=values[0],
        content=values[1],
        title=values[2],
        uri=uri,
        citation_label=protect_text(source.citation_label) if source.citation_label else None,
    )


def trace_text(value: str) -> str:
    """Telemetry must not expose rejected values or disrupt the primary result."""
    try:
        return protect_text(value)
    except GuardrailViolation:
        return "[CONTENT_WITHHELD]"
