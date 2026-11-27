"""The explicit taxonomy setup and safe XBRL input boundary."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from s2movement.cli import main
from scripts.fetch_taxonomy import TAXONOMY_FILE, fetch_taxonomy


def test_R001_official_package_is_recorded_and_contains_the_entry_point(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    reference = Path(__file__).resolve().parents[1] / "reference"
    with (reference / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        records = [
            row for row in csv.DictReader(stream) if row["filename"] == TAXONOMY_FILE
        ]
    assert len(records) == 1
    assert records[0]["version"] == "2.8.2 final"
    assert records[0]["sha256"] == (
        "a5090b571a8fc2b4297fa39d6bdb5498baa61a78add2b2ee95944dbfbbc39980"
    )

    isolated_reference = tmp_path / "reference"
    isolated_reference.mkdir()
    package = isolated_reference / TAXONOMY_FILE
    with ZipFile(package, "w") as archive:
        archive.writestr("META-INF/taxonomyPackage.xml", "<test/>")
        archive.writestr("2024-10-15/mod/ars.xsd", "<test/>")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    with (isolated_reference / "manifest.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerow({**records[0], "sha256": digest})
    monkeypatch.setattr(
        "scripts.fetch_taxonomy.reference_root", lambda: isolated_reference
    )

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("existing checked package must not use the network")

    monkeypatch.setattr("scripts.fetch_taxonomy.urlopen", no_network)
    assert fetch_taxonomy() == package
    with ZipFile(package) as archive:
        names = archive.namelist()
    assert any(name.endswith("META-INF/taxonomyPackage.xml") for name in names)
    assert any(name.endswith("2024-10-15/mod/ars.xsd") for name in names)


@pytest.mark.parametrize(
    "first,second,message",
    [
        ("opening.xbrl", "closing.xbrl", "metric/dimension mapping"),
        ("opening.xbrl", "closing.xlsx", "mixed XBRL/workbook pairs"),
    ],
)
def test_R001_unverified_input_is_refused_without_network(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    first: str,
    second: str,
    message: str,
) -> None:
    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("compare must not use the network")

    monkeypatch.setattr("scripts.fetch_taxonomy.urlopen", no_network)
    assert main(["compare", first, second, "--output-dir", str(Path("output"))]) == 2
    assert message in capsys.readouterr().err
