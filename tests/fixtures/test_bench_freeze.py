"""R-031–R-033 integrity checks for candidate and signed benchmark snapshots."""

import hashlib
from pathlib import Path

import pytest
from bench_integrity import inventory, verify


@pytest.mark.parametrize("change", ["changed", "missing", "extra", "sidecar", "anchor"])
def test_r031_frozen_population(tmp_path: Path, change: str) -> None:
    for case in ("1", "2a", "2b", "3", "4", "5"):
        directory = tmp_path / "packages" / case
        directory.mkdir(parents=True)
        for name in ("opening.xlsx", "closing.xlsx", "expected.yaml"):
            (directory / name).write_text(name)
    sidecar = tmp_path / "packages/2a/confirmations.json"
    sidecar.write_text("{}")
    settings = tmp_path / "thresholds.yaml"
    settings.write_text("{}")
    frozen = inventory(tmp_path)
    (tmp_path / "SHA256SUMS").write_bytes(frozen)
    digest = hashlib.sha256(frozen).hexdigest()
    anchor = tmp_path / "SIGNOFF.md"
    anchor.write_text(f"Current manifest SHA-256: `{digest}`\n")
    assert verify(tmp_path) == digest
    match change:
        case "changed":
            settings.write_text('{"factor": 1}')
        case "missing":
            (directory / "expected.yaml").unlink()
        case "extra":
            (directory / "extra.xlsx").touch()
        case "sidecar":
            sidecar.write_text('{"factor": 1}')
        case "anchor":
            anchor.write_text("The new digest has no sign-off record.\n")
    with pytest.raises(ValueError):
        verify(tmp_path)
