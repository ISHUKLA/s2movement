"""Explicit network setup for the pinned public EIOPA taxonomy archive."""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path
from urllib.request import urlopen

TAXONOMY_FILE = "eiopa_sii_2.8.2_taxonomy_with_external_files.zip"


def reference_root() -> Path:
    """Return the repository's public reference directory."""
    return Path(__file__).resolve().parents[1] / "reference"


def fetch_taxonomy() -> Path:
    """Fetch the taxonomy only when its checked local copy is absent."""
    reference = reference_root()
    with (reference / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["filename"] == TAXONOMY_FILE]
    if len(rows) != 1:
        raise ValueError("expected one official 2.8.2 taxonomy manifest record")
    record = rows[0]
    target = reference / TAXONOMY_FILE
    if (
        target.is_file()
        and hashlib.sha256(target.read_bytes()).hexdigest() == record["sha256"]
    ):
        return target
    staged = target.with_suffix(".download")
    digest = hashlib.sha256()
    try:
        with (
            urlopen(record["source_url"], timeout=60) as response,
            staged.open("wb") as output,
        ):
            while block := response.read(1024 * 1024):
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != record["sha256"]:
            raise ValueError("downloaded EIOPA taxonomy checksum differs from manifest")
        staged.replace(target)
    finally:
        staged.unlink(missing_ok=True)
    return target


if __name__ == "__main__":
    try:
        print(f"Taxonomy: {fetch_taxonomy()}")
    except (OSError, ValueError) as exc:
        print(f"s2movement: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
