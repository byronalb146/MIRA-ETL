from __future__ import annotations

import shutil
import urllib.request
import zipfile
from pathlib import Path

from mira_etl.config import SourceConfig


def obtain_zip(config: SourceConfig, period: str, work_dir: Path, local_zip: Path | None) -> Path:
    downloads_dir = work_dir / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    target = downloads_dir / f"{config.source}_{period}.zip"
    if local_zip is not None:
        shutil.copyfile(local_zip, target)
        return target

    url = config.download["url_template"].format(period=period)
    with urllib.request.urlopen(url, timeout=120) as response:
        target.write_bytes(response.read())
    return target


def extract_zip(zip_path: Path, work_dir: Path, source: str, period: str) -> Path:
    extract_dir = work_dir / "extracts" / source / period
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extract_dir)
    return extract_dir


def validate_required_files(config: SourceConfig, extract_dir: Path) -> None:
    missing = [name for name in config.files["required"] if not (extract_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required files: {', '.join(missing)}")
