from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator


def read_csv_rows(path: Path, *, delimiter: str, encoding: str) -> Iterator[dict[str, str | None]]:
    with path.open("r", encoding=encoding, newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        for row in reader:
            yield {clean_header(k): clean_value(v) for k, v in row.items() if k is not None}


def clean_header(value: str) -> str:
    return value.strip()


def clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned != "" else None
