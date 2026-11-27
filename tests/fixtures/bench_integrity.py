"""Verify the exact frozen population and the digest recorded for owner sign-off."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def inventory(root: Path) -> bytes:
    paths = {
        f"packages/{case}/{name}"
        for case in ("1", "2a", "2b", "3", "4", "5")
        for name in ("opening.xlsx", "closing.xlsx", "expected.yaml")
    }
    paths.update({"packages/2a/confirmations.json", "thresholds.yaml"})
    actual = {
        p.relative_to(root).as_posix()
        for p in (root / "packages").rglob("*")
        if p.is_file() or p.is_symlink()
    } | {"thresholds.yaml"}
    if paths != actual:
        raise ValueError(
            f"missing={sorted(paths - actual)}, extra={sorted(actual - paths)}"
        )
    lines = []
    for path in sorted(paths):
        source = root / path
        if source.resolve() != source.absolute() or not source.is_file():
            raise ValueError(f"expected a regular file: {source}")
        lines.append(f"{hashlib.sha256(source.read_bytes()).hexdigest()}  {path}\n")
    return "".join(lines).encode("ascii")


def verify(root: Path = HERE) -> str:
    digest_file = root / "SHA256SUMS"
    frozen = digest_file.read_bytes()
    if frozen != inventory(root):
        raise ValueError("benchmark differs from SHA256SUMS; owner review is required")
    digest = hashlib.sha256(frozen).hexdigest()
    anchor = re.findall(
        r"^Current manifest SHA-256: `([0-9a-f]{64})`$",
        (root / "SIGNOFF.md").read_text(),
        re.M,
    )
    if anchor != [digest]:
        raise ValueError("manifest digest differs from the current entry in SIGNOFF.md")
    return digest


if __name__ == "__main__":
    print(f"20 frozen benchmark files verified. Manifest SHA-256 {verify()}")
