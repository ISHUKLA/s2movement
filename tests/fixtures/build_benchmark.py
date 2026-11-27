"""Rebuild the independent benchmark in a new directory, leaving frozen files intact."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from bench_cases import period_cells
from bench_integrity import inventory
from bench_observations import movement_register, observations
from bench_oracle import expected_run
from bench_workbooks import HERE, RUNS, Cells, Citations, metadata, sha, write_period


def write_json(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def with_inventory(amounts: Cells, head: dict[str, str]) -> Cells:
    cells = amounts.copy()
    table = "S.01.02.01.01"
    for row, field in {
        "R0010": "undertaking_name",
        "R0020": "lei",
        "R0090": "reference_date",
        "R0110": "currency",
    }.items():
        cells[table, row, "C0010"] = head[field]
    for row, code in {
        "R0130": 1,
        "R0150": 2,
        "R0170": 2,
        "R0180": 1 if head["va_applied"] == "yes" else 2,
        "R0190": 2,
        "R0200": 2,
    }.items():
        cells[table, row, "C0010"] = str(code)
    families = {k[0][:7] for k in cells}
    statuses = {
        "R0010": "S.01.02",
        "R0030": "S.02.01",
        "R0110": "S.05.01",
        "R0220": "S.12.01",
        "R0370": "S.22.01",
        "R0410": "S.23.01",
        "R0460": "S.25.01",
        "R0500": "S.26.01",
        "R0510": "S.26.02",
        "R0520": "S.26.03",
    }
    for row, family in statuses.items():
        cells["S.01.01.01.01", row, "C0010"] = (
            "reported" if family in families else "not reported"
        )
    return cells


def expand(value: Any, refs: Citations) -> Any:
    if isinstance(value, dict):
        return {k: expand(v, refs) for k, v in value.items()}
    if isinstance(value, list):
        if (
            len(value) == 4
            and all(isinstance(v, str) for v in value)
            and value[0] in ("opening", "closing")
        ):
            return refs[tuple(value)]
        return [expand(v, refs) for v in value]
    return value


def unique_refs(groups: Iterable[list[list[str]]]) -> list[list[str]]:
    return [list(k) for k in dict.fromkeys(tuple(k) for group in groups for k in group)]


def make_case(dst: Path, case: str, settings: dict[str, Any]) -> None:
    dst.mkdir()
    opening, closing = period_cells(case, False), period_cells(case, True)
    refs: Citations = {}
    for period, financial in (("opening", opening), ("closing", closing)):
        cells = with_inventory(financial, metadata(case, period))
        refs.update(write_period(dst / f"{period}.xlsx", case, period, cells))
    if case == "2a":
        write_json(
            dst / "confirmations.json",
            {
                "schema_version": "0.1",
                "confirmations": [
                    {
                        "period": "opening",
                        "file_id": "opening.xlsx",
                        "factor": "1000",
                        "target_unit_scale": "1",
                        "reviewer": "Synthetic benchmark reviewer",
                        "reason": (
                            "Opening reports whole thousands of EUR. "
                            "Convert to EUR for this comparison."
                        ),
                        "evidence": (
                            "opening.xlsx Metadata!B11:B13 and "
                            "closing.xlsx Metadata!B11:B13."
                        ),
                    }
                ],
            },
        )
    runs = []
    for rid in RUNS[case]:
        run = expected_run(case, rid, opening, closing)
        gate = run["gate"]
        gate["metadata"] = [ref for k, ref in refs.items() if k[1] == "Metadata"]
        if case == "2a":
            gate["unit_evidence"] = [
                [p, "Metadata", "money_unit_scale", "value"]
                for p in ("opening", "closing")
            ]
            if rid.endswith("confirmed"):
                gate["confirmation"] = {
                    "file": "confirmations.json",
                    "sha256": sha(dst / "confirmations.json"),
                    "factor": "1000",
                    "result_unit": "EUR",
                    "result_unit_scale": "1",
                }
        if case == "2b":
            gate["warning_evidence"] = {
                "va_status_changed": [
                    [p, "S.01.02.01.01", "R0180", "C0010"]
                    for p in ("opening", "closing")
                ],
                "va_tp_impact_material_shift": [
                    [p, "S.22.01.01.01", "R0010", "C0070"]
                    for p in ("opening", "closing")
                ]
                + [["opening", "S.22.01.01.01", "R0010", "C0010"]],
            }
        if case == "3":
            gate["warning_evidence"] = {
                "closing_missing_S.25.01": [
                    ["closing", "S.01.01.01.01", "R0460", "C0010"]
                ]
            }
        if rid.endswith("stop"):
            # Make the early return auditable without scoring post-gate checks.
            continued = expected_run(case, "02a-confirmed", opening, closing)
            run["checks_not_run"] = [
                {"id": c["id"], "status": "withheld", "reason": "unit_scale_mismatch"}
                for c in continued["comparisons"]
            ]
            run.update(
                flags=[],
                abstentions=[],
                accounted=[],
                exclusions=[],
                joint_questions=[],
            )
        else:
            run.update(movement_register(case, opening, closing, settings["rules"]))
            run.update(
                observations(case, opening, closing, settings["rules"], run["bridges"])
            )
            for tier in run["tier_limits"]:
                if tier["status"] == "binding" and tier["rule"] in (
                    "article82_3",
                    "article82_1_b",
                    "article82_1_c",
                ):
                    run["flags"].append(
                        {
                            "id": f"tier_constraints/{tier['id']}",
                            "rule": "tier_constraints",
                            "status": tier["status"],
                            "rule_source": tier["rule_source"],
                            "settings": "thresholds.yaml#rules/tier_constraints",
                            "citations": unique_refs(
                                tier[k]["citations"]
                                for k in ("supply", "eligible", "denominator")
                            ),
                        }
                    )
        runs.append(expand(run, refs))
    write_json(dst / "expected.yaml", {"version": 1, "case": case, "runs": runs})


def build(out: Path) -> None:
    out = out.resolve()
    if out.exists() or out.is_relative_to(HERE):
        raise ValueError("choose a new directory outside tests/fixtures")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as staging:
        root = Path(staging) / "candidate"
        dest = root / "packages"
        dest.mkdir(parents=True)
        shutil.copyfile(HERE / "thresholds.yaml", root / "thresholds.yaml")
        settings = json.loads((root / "thresholds.yaml").read_text())
        for case in RUNS:
            make_case(dest / case, case, settings)
        (root / "SHA256SUMS").write_bytes(inventory(root))
        root.rename(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)
