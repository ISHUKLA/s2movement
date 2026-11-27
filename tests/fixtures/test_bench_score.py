"""R-032/R-033 regressions for the benchmark judge, using separate toy inputs."""

import hashlib
from copy import deepcopy
from pathlib import Path

from bench_score import Audit, Excel, Obj, Score, Sources, score_run
from openpyxl import Workbook


def source_pair(directory: Path) -> tuple[Sources, Obj]:
    for period in ("opening", "closing"):
        book = Workbook()
        book.remove(book["Sheet"])
        meta = book.create_sheet("Metadata")
        for row in (
            ("field", "value"),
            ("currency", "EUR"),
            ("money_unit_scale", "1"),
            ("reference_date", "2024-12-31"),
        ):
            meta.append(row)
        contexts = book.create_sheet("Contexts")
        contexts.append(["context_id", "entity_lei", "reference_date", "dimensions"])
        contexts.append(["fixture", "test", "2024-12-31", '{"basis":"A"}'])
        ws = book.create_sheet("Toy")
        for entry in (
            ("table", "Toy.table"),
            ("context", "fixture"),
            ("row/column", "C"),
            ("R_a", 15),
            ("R_b", 15),
        ):
            ws.append(entry)
        book.save(directory / f"{period}.xlsx")
        book.close()
    expected: Obj = {
        "period": "opening",
        "sheet": "Toy",
        "cell": "B4",
        "file_id": "opening.xlsx",
        "template": "Toy",
        "table": "Toy.table",
        "row": "R_a",
        "column": "C",
        "source_sha256": hashlib.sha256(
            (directory / "opening.xlsx").read_bytes()
        ).hexdigest(),
        "context_id": "fixture",
        "dimensions": {"basis": "A"},
        "reported_value": "15",
    }
    return Sources(directory), expected


def example_view() -> Excel:
    def example(as_values: bool) -> Workbook:
        book = Workbook()
        book.remove(book["Sheet"])
        raw = book.create_sheet("Raw_opening")
        raw.append(["sheet", "cell", "reported_value"])
        raw.append(["Toy", "B4", 15])
        raw.append(["Toy", "B5", 15])
        calc = book.create_sheet("Bridge")
        calc.append(["line id", "result"])
        for row, formula in (
            ("correct", "='Raw_opening'!C2"),
            ("wrong_row", "='Raw_opening'!C3"),
            ("static", 15),
            ("constant", "=15"),
        ):
            calc.append([row, 15 if as_values else formula])
        return book

    return Excel(example(False), example(True))


def test_r033_wrong_location_context_and_static_formulas(tmp_path: Path) -> None:
    sources, cite = source_pair(tmp_path)
    wb = example_view()
    score = Score()
    audit = Audit(score, sources, wb, "toy")
    expected = {"value": "15", "unit": "EUR", "citations": [cite]}
    actual = {**expected, "status": "value"}
    cell = wb.formulas["Bridge"]["B2"]
    assert audit.amount("correct", expected, actual, cell)
    for pos in ("B3", "B4", "B5"):
        assert not audit.amount(pos, expected, actual, wb.formulas["Bridge"][pos])
    altered = {**actual, "citations": [{**cite, "dimensions": {"basis": "B"}}]}
    assert not audit.amount("context", expected, altered, cell)
    assert not audit.amount("sign", expected, {**actual, "value": "-15"}, cell)
    assert score.issues["sign_inversions"] == ["sign"]
    assert score.matched["numeric_values"] == 1


def test_r032_missing_outputs_stay_in_denominators(tmp_path: Path) -> None:
    sources, cite = source_pair(tmp_path)
    bridge = {
        "id": "toy",
        "tolerance": "1",
        "residual_status": "pass",
        "lines": [
            {
                "id": name,
                "role": name,
                "value": value,
                "status": "value",
                "citations": [cite],
                "unit": "EUR",
            }
            for name, value in (("opening", "15"), ("closing", "15"), ("residual", "0"))
        ],
    }
    key = {"id": "demo", "gate": {"status": "pass"}, "bridges": [bridge]}
    score = Score()
    score_run(score, sources, key, {}, None)
    assert score.expected["bridges_tied"] == 1 and score.matched["bridges_tied"] == 0
    assert score.expected["citations"] == 4 and score.matched["citations"] == 0
    assert score.expected["numeric_values"] == 3
    assert score.issues["omitted_bridges"] == ["demo/toy"]
    assert len(score.issues["omitted_lines"]) == 3
    assert not score.report()["deterministic_gates_pass"]


def test_d9_false_abstentions_are_report_only_and_stops_need_reason(
    tmp_path: Path,
) -> None:
    sources, _ = source_pair(tmp_path)
    key = {
        "id": "demo",
        "gate": {"status": "blocked", "stops": ["unit_scale_mismatch"]},
        "accounted": [{"id": "F01"}],
    }
    out = {"gate": {"status": "blocked", "stops": ["unit_scale_mismatch"]}}
    score = Score()
    score_run(score, sources, key, out, None)
    baseline = deepcopy(score.issues)
    new = Score()
    score_run(new, sources, key, {**out, "abstentions": [{"id": "F01"}]}, None)
    assert baseline == new.issues and score.matched == new.matched
    assert new.false_abstentions == ["demo/F01"]
    assert new.report()["R-034"] == "not yet measured"
    bad = Score()
    score_run(
        bad, sources, key, {"gate": {"status": "blocked", "stops": ["other"]}}, None
    )
    assert bad.matched["stops"] == 0


def test_r032_conforming_bridge_passes_and_an_unexpected_warning_fails(
    tmp_path: Path,
) -> None:
    sources, cite = source_pair(tmp_path)
    closing = {
        **cite,
        "period": "closing",
        "file_id": "closing.xlsx",
        "source_sha256": hashlib.sha256(
            (tmp_path / "closing.xlsx").read_bytes()
        ).hexdigest(),
    }
    lines: list[Obj] = []
    for name, value, refs in [
        ("opening", "15", [cite]),
        ("change", "0", [cite, closing]),
        ("residual", "0", [cite, closing]),
        ("closing", "15", [closing]),
    ]:
        lines.append(
            {
                "id": name,
                "role": "movement" if name == "change" else name,
                "status": "value",
                "value": value,
                "unit": "EUR",
                "citations": refs,
            }
        )
    key = {
        "id": "demo",
        "gate": {"status": "pass"},
        "bridges": [
            {
                "id": "toy",
                "unit": "EUR",
                "tolerance": "1",
                "residual_status": "pass",
                "lines": lines,
            }
        ],
    }
    observed = {
        "id": "toy",
        "lines": deepcopy(lines),
        "residual_check": {
            "status": "pass",
            "signed_discrepancy": deepcopy(lines[2]),
            "tolerance": {"value": "1", "unit": "EUR"},
        },
    }

    def model(as_values: bool) -> Workbook:
        book = Workbook()
        book.remove(book["Sheet"])
        for period in ("opening", "closing"):
            sheet = book.create_sheet(f"Raw_{period}")
            sheet.append(["sheet", "cell", "reported_value"])
            sheet.append(["Toy", "B4", 15])
        b = book.create_sheet("Toy")
        b.append(["line_id", "result"])
        formulas = [
            "=Raw_opening!C2",
            "=Raw_closing!C2-Raw_opening!C2",
            "=B5-B2-B3",
            "=Raw_closing!C2",
        ]
        for line, expr in zip(lines, formulas, strict=True):
            b.append([line["id"], int(line["value"]) if as_values else expr])
        return book

    excel = Excel(model(False), model(True))
    out = {"gate": {"status": "pass"}, "bridges": [observed], "abstentions": ["F01"]}
    score = Score()
    score_run(score, sources, {**key, "accounted": [{"id": "F01"}]}, out, excel)
    assert score.report()["deterministic_gates_pass"], score.issues
    assert score.false_abstentions == ["demo/F01"]
    warned = Score()
    score_run(warned, sources, key, {**out, "warnings": ["unexpected"]}, excel)
    assert not warned.report()["deterministic_gates_pass"]
