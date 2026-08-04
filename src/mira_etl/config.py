from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceConfig:
    source: str
    country_code: str
    source_system: str
    connector_version_env: str
    download: dict[str, Any]
    files: dict[str, list[str]]
    csv: dict[str, Any]

    @classmethod
    def load(cls, config_dir: Path, source: str) -> "SourceConfig":
        path = config_dir / f"{source}.json"
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return cls(**payload)

    def delimiter_for(self, filename: str) -> str:
        delimiters = self.csv.get("delimiters", {})
        return delimiters.get(filename, self.csv.get("default_delimiter", ";"))

    @property
    def encoding(self) -> str:
        return self.csv.get("encoding", "utf-8-sig")
