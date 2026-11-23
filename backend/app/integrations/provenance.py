"""Provenance for evidence records: where exactly a record came from, and a fingerprint of the raw payload.

Only source parsers call `make_provenance`, so every EvidenceRecord with provenance originates from a real API
response. LLM output never produces EvidenceRecords (its schemas contain only text and record-ID references).
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from typing import Any

from app.models.evidence import Provenance

PARSER_VERSION = "2026.11.23"


def payload_digest(payload: Any) -> str:
    """SHA-256 of the raw source item (canonical JSON, or serialised XML)."""
    if isinstance(payload, ET.Element):
        raw = ET.tostring(payload, encoding="utf-8")
    elif isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode()
    else:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def make_provenance(source_module: str, api_url: str, payload: Any) -> Provenance:
    return Provenance(
        api_url=api_url,
        payload_sha256=payload_digest(payload),
        parser=f"{source_module}@{PARSER_VERSION}",
    )
