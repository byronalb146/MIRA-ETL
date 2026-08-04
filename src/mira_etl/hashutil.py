from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stable_id(*parts: object, prefix: str = "") -> str:
    value = "|".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}{digest}" if prefix else digest
