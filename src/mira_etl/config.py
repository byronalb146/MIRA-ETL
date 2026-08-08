from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceConfig:
    source: str
    country_code: str
    source_system: str
    connector_version: str
    download: dict[str, Any]
    files: dict[str, list[str]]
    csv: dict[str, Any]
    processing: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_dir: Path, source: str) -> "SourceConfig":
        path = config_dir / f"{source}.json"
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return cls(**payload)

    def delimiter_for(self, filename: str) -> str:
        delimiters = self.csv.get("delimiters", {})
        return delimiters.get(filename, self.csv.get("default_delimiter", ";"))

    def source_url_for_period(
        self,
        period: str,
    ) -> str:

        if len(period) != 6 or not period.isdigit():
            raise ValueError(
                f"Invalid period '{period}'. "
                "Expected YYYYMM."
            )

        year = period[:4]
        month = str(int(period[4:6]))

        return self.download[
            "url_template"
        ].format(
            period=period,
            year=year,
            month=month,
        )

    @property
    def encoding(self) -> str:
        return self.csv.get("encoding", "utf-8-sig")

    @property
    def batch_size(self) -> int:
        value = int(self.processing.get("batch_size", 250))
        if value < 1:
            raise ValueError("processing.batch_size must be greater than zero")
        return value

    @property
    def record_limit(self) -> int | None:
        value = self.processing.get("record_limit")
        if value is None:
            return None
        limit = int(value)
        if limit < 1:
            raise ValueError("processing.record_limit must be greater than zero")
        return limit
