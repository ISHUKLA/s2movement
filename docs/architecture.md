# Approved architecture — first slice

The owner approved this design on 25 November 2026. [Revision 2 of the specification](spec.md) governs. R-009–R-011, R-022 and decisions D2, D3 and D8 apply in the first slice; they are not deferred to the finished product. The source inventory remains preliminary; the slice is limited to the specifically verified supervisory cells below.

## Boundaries and data flow

`normalized workbook → workbook adapter → fact ledger → gate and checks → bridge definition/evaluation → validation → Excel + JSON`

An XBRL adapter can later produce the same ledger. After ingestion, neither checks, bridges nor renderers inspect input-format objects. The deterministic command has no network, model, telemetry or external-data calls. Future opt-in commentary is a separate consumer of validated JSON and is outside this slice.

The normalized workbook contract is in [input-format.md](input-format.md). Each input states whether it is a supervisory or public-disclosure variant. Mapping selection uses taxonomy version, physical table, variant and applicable context; a coincident row and column do not prove equivalence.

## Fact ledger and evidence (R-004, R-022, D8)

An immutable ledger record represents **one reported source cell**. It contains:

- The period and the template family, full physical table, row and column; source variant and taxonomy version; the canonical entity, reporting date and relevant dimensions/context. A four-part coordinate is not assumed unique.
- Original value and type, currency or other unit, unit scale and reported precision. Monetary values are `Decimal`; text, dates, identifiers and enumerated metadata retain their appropriate types. Unknown precision is explicit, never inferred from the number of displayed digits.
- A source locator: stable input file identifier and SHA-256, actual worksheet and cell address for a workbook, or instance, fact identity and context/unit references for XBRL. The hash is provenance, not a substitute for the locator.
- Any confirmed conversion: original value and unit, factor, resulting unit and value, reason, and the reviewer confirmation/evidence locator. The original fact is never overwritten.

Header metadata is also stored as cited facts. A value declared at `Metadata!B…` is cited there; an S.01.02 fact is cited at its real template/source location. A declaration is not presented as if it came from an official template. If both are present, conflicting values stop the affected gate and both sources remain visible. Public workbooks need their own cited metadata; they do not acquire absent S.01.02 cells by assumption.

The key includes physical table and context as well as period/template/row/column. Reject duplicate claims for the same key unless their distinguishing context is explicitly represented; never take the first match. Derived results carry the union of all leaf citations, the expression, units and sign convention. Conversions also cite the confirmation. Static rules and tolerances cite their specification or mapping source and the source precision on which the calculation depends.

## Comparability, consistency and conversion (R-005–R-008, D2)

The gate checks the actual cited metadata before a bridge: two consecutive annual dates, supported taxonomy and variant, the same LEI, currency and solo perimeter, Standard Formula, required S.02.01 and S.23.01, and compatible units. Missing evidence does not become a favourable default. A changed LTG/transitional or other specified condition is surfaced as a warning where R-006 permits continuation.

Different scales without a documented conversion are a hard stop. An acknowledgement never clears it. `--confirmations` accepts an explicit JSON record with the affected period/file, exact factor, target scale, reason, reviewer and evidence. The conversion is accepted only for the same currency; it is not a foreign-exchange conversion. `--corrections` accepts source-evidenced metadata changes with the original value, corrected value, reason, reviewer and evidence. The loader verifies that the original value matches the input, retains both values and the correction citation, then reruns the gate. A corrected LEI or reference date must also agree with the normalized workbook contexts. Otherwise the affected results remain blocked. Neither option edits the source workbook.

After the gate, each cross-template comparison has named left and right operands, the required context, an ordered discrepancy `left − right`, a tolerance and a status. It reports the cited operands, signed discrepancy and tolerance on both pass and fail. Failed comparisons withhold only dependent deltas; unavailable comparisons identify the missing evidence and leave unaffected results usable. In the slice, compare S.02.01 R1000/C0010 with S.23.01 R0700/C0060 **at both dates**, using the whole-undertaking context, before the excess bridge. The two full table addresses are in the slice section below. Other R-008 comparisons are identified as not implemented, not reported as passed.

## Statuses across all representations

Use a discriminated result, never an untyped nullable number. The following is contract notation, not executable code. A hard-stop gate has its own `blocked` outcome; a line prevented by that gate is `withheld` with the gate cause. A failed bridge residual is a **value** with a separate failed check, so the break remains visible.

| Meaning | Python result | JSON result | Excel result cell and adjacent status |
| --- | --- | --- | --- |
| Value, including a genuine zero | `Value(Decimal, unit, sign, citations)` | `{"status":"value","value":"0", ...}` | A live numeric formula, with a numeric cached result; status `value`. |
| Missing template | `Unavailable(missing_template, period, reason)` | `{"status":"unavailable","missing_template":"S.12.01","period":"closing","reason":"not supplied"}` | Formula yields `Unavailable: S.12.01 (closing)`; status `unavailable`. |
| A required check or gate failed | `Withheld(check_id, reason)` | `{"status":"withheld","check_id":"...","reason":"consistency check failed"}` | Formula yields `Withheld: <check id>`; status `withheld`. |
| Evidence cannot support a conclusion | `Indeterminate(reason, citations)` | `{"status":"indeterminate","reason":"...","citations":[...]}` | Formula yields `Indeterminate: <reason>`; status `indeterminate`. |

Non-value outcomes have no numeric payload; JSON status and reason are mandatory. Python arithmetic rejects them. Formula generation tests prerequisite statuses before doing arithmetic and emits the corresponding text. There is no blank, silent zero, `IFERROR(...,0)` or `SUM` that ignores a missing text operand. When multiple prerequisites fail, a documented stable ordering selects the displayed primary reason and the full cause list remains in JSON/dashboard. A zero is possible only when supported arithmetic or an explicitly reported zero produces it.

For example, if `C5` is the calculated status and `D5` contains the cause, a liability-contribution cell could contain this formula (the raw positions are illustrative):

```excel
=IF(C5="value",'Raw_opening'!L7-'Raw_closing'!L7,IF(C5="unavailable","Unavailable: "&D5,IF(C5="withheld","Withheld: "&D5,IF(C5="indeterminate","Indeterminate: "&D5,"Indeterminate: invalid status"))))
```

With a value status it returns the cited numeric contribution; for each other status it returns the named text and cause. `C5` itself is a formula over the gate, check and prerequisite status cells, not a manually asserted success. Its cached value and this formula's cached result are supplied from the evaluated result and verified by recalculation.

## Tolerance and arithmetic (R-008, R-011, D3)

Tolerance is a first-class object with decimal magnitude, unit, policy, supporting precision/conversion evidence and source rule. Every comparison **and** bridge declares one. For like-for-like money with no conversion, it is one reporting unit. Following a confirmed conversion, it is one unit of the coarser source precision expressed in the common unit. For the S.23.01 reported ratio, it is one unit at the fact's declared precision: the owner selected XBRL `decimals`, not lexical digits. A normalized workbook supplies that precision explicitly. `INF` and missing ratio precision remain unresolved as recorded in [VERIFICATION.md](../mappings/VERIFICATION.md); no pass/fail is inferred from a missing tolerance.

For a bridge, the signed residual is `closing − opening − sum(signed movements)` and passes exactly when `abs(residual) ≤ tolerance`. Both the residual and tolerance are shown even on a pass. The closing equation still contains the residual on failure; the other lines are not adjusted to absorb it. Cross-template failures withhold dependent bridge lines; a bridge's own nonzero residual instead remains visible and fails the bridge check.

### Excel numeric boundary

Excel numbers have finite binary floating-point precision, whereas the ledger uses decimal arithmetic. For this slice, accept whole reporting-unit monetary inputs and conversions that can be expressed as integral multipliers into a common unit. Require the absolute value of every original amount, converted amount and intermediate integer to be at most `999999999999999`; reject the affected run with an explicit precision/representation error otherwise. This conservative, observable boundary makes the slice's addition, subtraction and integer conversion exactly representable. Do not round an out-of-range value to make it fit. A later extension for other precisions requires its own proven representation.

The future ratio bridge needs additional work: a quotient may not be exactly representable as a finite Excel number or `Decimal`. Keep exact numerator/denominator evidence and comparisons possible in the model, and do not assert exact Excel/JSON equivalence for fractional ratios until an implementation proves it without changing D3 or R-021. The first slice checks the reported ratio only if that precision issue is explicitly resolved; otherwise it is **indeterminate**, never a pass. This does not make its unimplemented ratio bridge available.

## Declarative bridges and the first slice

A versioned bridge definition is an ordered list of line identifiers, labels, expression trees, source selectors, dependencies and sign/unit rules; it also declares the residual expression and tolerance. The same expression tree is interpreted with `Decimal` for Python and compiled into live formulas referencing the raw tabs. It is not copied into a separately maintained Excel calculation. Expressions are limited to explicitly supported operations, with unit and status checks. Shared selectors resolve to ledger facts, not directly to workbook cells.

The **first slice**, not the full R-016 bridge, uses these supervisory S.02.01.01.01 cells, all C0010, at each date. Each cell is selected with its verified DPM signature: R0070 uses `s2c_VG=s2c_x80` and `s2c_BL=s2c_x91`; R0220 uses `s2c_VG=s2c_x80` and `s2c_BL=s2c_x119`; R0500, R0900 and R1000 use `s2c_VG=s2c_x80` without BL. In XBRL the VG member has QNames `s2c_dim:VG=s2c_AM:x80`; the BL members use `s2c_dim:BL=s2c_LB:x91` or `s2c_LB:x119`. S.23.01.01.02 R0700/C0060 uses the same VG member and the EIOPA identical-datapoints coordinate context Z0001. The normalized workbook retains the full table and context per block.

| Line | Expression | Evidence |
| --- | --- | --- |
| Opening and closing excess | Reported R1000 | `cells.csv` and the matched S.23 comparison in `VERIFICATION.md` §2. |
| Investments movement | ΔR0070 | R0070 excludes linked assets; AT label and BV320_1-1. |
| Linked assets movement | ΔR0220 | AT label and BV320_1-1. |
| Other assets movement | Δ(R0500 − R0070 − R0220) | Derived remainder of total assets, not an independently reported category or an additional reported subtotal. BV320_1-1 lists R0070 and R0220 among the non-overlapping R0500 components. |
| Liabilities contribution | −ΔR0900 | Total liabilities, with its sign in the excess equation. |
| Residual | closing R1000 − opening R1000 − all four movements | Separately displayed and tested against D3. |

The active EIOPA validation workbook has `BV320_1-1` at worksheet row 3318 for the asset components and `BV330_1-1` at row 3311 for R1000 = R0500 − R0900, all C0010; see the source manifest. The opening/closing S.23 counterpart is S.23.01.01.02 R0700/C0060. A public variant requires its own matched mapping; the first slice need not claim public coverage merely because a similarly named cell exists.

The selected mapping rows and their active validation rules are recorded in `mappings/2.8.2/relationships.csv`; the exact context and sign evidence are in `mappings/VERIFICATION.md`. Other signs, subtotals and comparisons remain open. Do not turn the inventory into blanket authorization. No bridge relies on an unresolved mapping.

### Deliberate break versus failed consistency

For the visible-break test, change the closing R1000 and its matching S.23 R0700 together while leaving closing assets and liabilities unchanged. The cross-template check remains comparable, and the bridge shows the resulting nonzero residual and failure without changing its other lines. A separate test changes only one side of the cross-template check and expects dependent deltas to be withheld. For the live-formula test, change closing R0900 alone: the liabilities contribution and residual change by equal and opposite effects while the reported closing excess and the R-008 cross-template check remain unchanged.

## Excel workbook (R-010, R-011, R-022)

- `Summary` is the dashboard: cited period metadata, gate outcomes, warnings, each comparison's operands, signed discrepancy and tolerance, and bridge status/residual/tolerance. Hard stops are visible even if no bridge can be computed.
- `Raw_opening` and `Raw_closing` each contain one row per ledger fact: fact key/context, input file/sheet/cell, reported value, source currency/scale/precision, conversion confirmation and reason. For a converted monetary fact, show the original value, factor and target unit alongside a **live converted-value formula**; calculation cells reference that formula, which references the original raw value and factor. Unconverted raw source values are literals.
- Calculation tabs hold the ordered bridge lines, dependencies, formula results, units, statuses and citations. All calculated financial cells are formulas over raw cells or other formula cells that ultimately resolve to raw cells. Raw inputs and non-financial labels are not presented as calculated results.
- Use explicit status cells and status-aware formulas, including for conversion and residual. Write the exact Python result as the formula's cache and request recalculation on open; test both the cache and the recalculated result. A later edit to a raw cell updates the dependent formulas. A changed workbook must be recalculated before trusting its cached values.

For example, a cited reported value of `1234` in thousands of EUR, with confirmed factor `1000` into EUR units, appears on its raw row as the original `1234`, original scale/precision, factor `1000`, target `EUR`, confirmation/evidence and reason. If those are in `H2`, `J2` and the conversion status/cause are in `M2`/`N2`, the converted cell is `=IF(M2="value",H2*J2,"Withheld: "&N2)` and displays `1234000`. A bridge formula references that converted cell. The precision of one source thousand becomes a tolerance contribution of `1000` EUR where D3's coarser-precision rule applies. Both the source cell and the confirmation are cited.

The implementation keeps **openpyxl** for reading inputs and inspecting tests, **pydantic** for validated boundary models and **pytest** for tests, on Python 3.12. It adds **XlsxWriter** for output because its `write_formula` accepts an explicit numeric or text cached result; [openpyxl does not calculate formulas](https://openpyxl.readthedocs.io/en/stable/simple_formulae.html) and XlsxWriter's default cache would otherwise be zero. Always supply the cache rather than using that default. [XlsxWriter formula results](https://xlsxwriter.readthedocs.io/working_with_formulas.html#formula-results) · [Excel precision](https://support.microsoft.com/en-us/excel/excel-specifications-and-limits).

## JSON contract (R-009, R-022, D8)

JSON is UTF-8, deterministically ordered and versioned. Decimal values are canonical decimal **strings**, avoiding binary conversion. No generated time, random identifier or absolute machine-specific path is required for identical inputs and settings. The core shape is:

```json
{
  "schema_version": "0.1",
  "inputs": [{"file_id": "opening.xlsx", "sha256": "<digest>", "period": "opening", "variant": "supervisory"}],
  "metadata": [{"name": "currency", "status": "value", "value": "EUR", "citations": [{"file_id": "opening.xlsx", "sheet": "Metadata", "cell": "B11"}]}],
  "gate": {"status": "pass", "checks": [], "conversions": []},
  "comparisons": [{"id": "opening_excess", "status": "pass", "left": "<cited amount>", "right": "<cited amount>", "signed_discrepancy": "<cited amount>", "tolerance": "<cited tolerance>"}],
  "bridges": [{"id": "excess", "lines": [{"id": "liabilities_movement", "result": {"status": "value", "value": "-60", "unit": {"kind": "money", "currency": "EUR", "scale": "1"}, "sign": "positive increases excess", "citations": [{"period": "opening", "template": "S.02.01", "table": "S.02.01.01.01", "row": "R0900", "column": "C0010", "context": "solo", "file_id": "opening.xlsx", "sheet": "S.02.01", "cell": "B7"}, {"period": "closing", "template": "S.02.01", "table": "S.02.01.01.01", "row": "R0900", "column": "C0010", "context": "solo", "file_id": "closing.xlsx", "sheet": "S.02.01", "cell": "B7"}]}}], "residual_check": {"status": "pass", "signed_discrepancy": "<cited amount>", "tolerance": "<cited tolerance>"}}],
  "warnings": [],
  "flags": []
}
```

The angle-bracketed strings above denote required full result objects, not values in an actual output. Each amount object contains status, decimal value, unit/scale, sign convention, all contributing source citations and, when derived, an expression identifier. A tolerance object additionally contains the policy and cited input precision/conversion evidence. Missing/withheld/indeterminate objects use the status contract above. Every financial number, including a gate operand, residual and threshold, is represented by such an object; a number never appears as an unsupported scalar. Metadata and confirmation evidence have their own real locators.

Before writing either output, resolve every source citation against the ledger and input locator, verify its value/context/unit, recompute derived evidence and check that generated formula references match the expression tree. A changed value, coordinate, period or formula must fail validation or withhold the affected output. The Excel and JSON views derive from the same evaluated results and evidence.

## CLI and test contract

Invocation: `s2movement compare opening.xlsx closing.xlsx --output-dir output/`, optionally with `--confirmations confirmations.json` or `--corrections corrections.json`. Default mode is deterministic and offline. It writes the workbook and JSON together after validation. A comparison/bridge failure is reported in the outputs and by a nonzero exit code; a hard stop leaves affected movements and residual withheld. No commentary option is part of this slice.

The hand-written workbooks in `tests/data/` and the independent expected-value assertions in `tests/test_slice.py` exercise the slice. They are not the Step 4 signed-off benchmark. The future benchmark builder remains independent of `src/`; after Step 4 sign-off its checksum manifest and owner approval rules apply unchanged.

The single `make check` includes:

1. **R-010 recalculation:** render, then recalculate a copy using LibreOffice headless with a private temporary profile. Enumerate every formula cell, compare all numeric **and text/status** results with Python's expectations and assert no missing cache, spreadsheet error or formula replaced by a constant. openpyxl alone is not the engine.
2. **R-010 live formulas:** alter only the copied closing R0900 raw value, recalculate, and independently assert the expected changes in the liability contribution and residual.
3. **R-011 visible break:** use the paired S.02/S.23 closing break described above; check signed residual, failed status and unchanged other lines. Separately test a cross-template mismatch withholding its dependent lines.
4. **R-009 repeatability:** run twice with identical inputs/settings; compare JSON bytes and workbook cells, formulas, types, cached values and relevant styles cell by cell. Container ZIP metadata/timestamps may differ and are excluded from the workbook comparison.
5. **R-009 no network:** run the complete deterministic CLI under macOS `sandbox-exec` with networking denied. A CPython audit hook records and fails on Python socket/DNS calls, and the app run also fails on child-process creation. The harness verifies that standard-library calls, caught errors and a Python subprocess attempt are observed, and that a direct native socket attempt is blocked by the OS sandbox. A missing backend or failed self-test fails the suite.
6. **R-022 and D2/D3/D8:** the JSON and workbook include actual input locators, full template/row/column plus context, declared tolerances, discrepancy and correction/conversion evidence. The D2 correction test confirms that an unsupported scope blocks the run and a matching source-evidenced correction reruns the gate. The tests do not sign off the future mappings or Step 4 benchmark.

`make check` verifies LibreOffice 26.2.5.2 and the macOS `sandbox-exec` backend; a missing or different version fails with an actionable assertion. The Python audit hook observes Python-level connection attempts, including from child Python processes. The OS sandbox blocks direct native connections; macOS does not provide a reliable per-process record for every raw syscall, so the core also has a test that rejects imports of the standard network and raw-socket modules. The test suite is deliberately tied to the verified macOS backend and is not yet portable.

Formula tests create and recalculate workbooks and a private LibreOffice profile in fresh OS temporary directories, then clean them up. `make check` does not modify repository files. ZIP container timestamps are not pinned; repeatability compares all workbook cells, formulas, cached results, types and styles, while JSON is compared byte for byte.

## Remaining limits

This approval does not sign off Step 2, settle the fractional-ratio representation, freeze benchmarks or authorize claims that unsupported bridges work. The implementation is limited to the demonstrated S.02.01 excess bridge and its S.23.01 consistency comparison. The R-008 ratios, other templates and later bridges remain unavailable until their mappings and arithmetic are verified.

## Technical-provision output contract · R-012–R-015

The life and health SLT bridge sheets each have a component schedule alongside their signed bridge. Opening and closing net best estimate are calculated as gross best estimate less best-estimate recoverables. The component total counts whole TP less its recoverables, net best estimate, risk margin and any signed TMTP allocations once. The additive bridge uses the gross components and deductions. The subtotal is identified in the schedule.

S.12.01 detail retains each reportable row and column. Guarantee splits follow the source cells. The linked risk-margin total remains at C0030. S.22.01 appears beside each TP bridge in a separate undertaking-wide scenario schedule, with opening, closing and changes in reported impacts. Its heading identifies the whole-undertaking scope.

The JSON `schedules` array exposes stable IDs, categories, opening and closing values, movements, statuses, source citations and Excel locations. Each `movement_difference` has two `operands` containing schedule IDs. Its value is the first schedule's movement minus the second schedule's movement. R-015 compares `linked/R0220` with each of `linked/R0340`, `linked/R0700`, `linked/R0710` and `linked/R0720`. These observed differences supply facts for Step 9. The existing `linked/observed_difference` holds the aggregate comparison defined by the frozen linked-divergence rule.

The JSON `linked_pairing` object exposes the materiality decision and the relevant movement and difference IDs. Each date records cited linked assets, total assets and the threshold, plus the source of its settings. The frozen rule qualifies either date when absolute linked assets in EUR exceed the greater of EUR 100,000 and 5% of same-date total assets. Equality is below the trigger. Confirmed scale conversions feed this comparison through the ledger. A nonpositive denominator, missing operand or unsupported threshold currency gives an indeterminate assessment. Available movements remain visible under that assessment. The `Linked_pairing` worksheet shows the assessment and the signed comparisons with live formulas.

## Own funds and limits · R-016–R-018

Each balance-sheet bridge line publishes `reported_inputs` and `covered_rows`. The versioned bucket catalogue records every row and the subtotal tree. The calculation uses each bucket's reported roots. The two date-specific own-funds reconciliations and the annual eligible-own-funds bridge share their adjustment definitions. Unsupported splits appear in the summary and JSON with their aggregate citations.

The `tier_limits` array contains six assessments, covering three limits at each date. Each assessment supplies available and eligible amounts, its denominator, legal bound, headroom, observed eligible-minus-available adjustment, source precision, exact reported compliance and attributed effect. The legal operator, article and source come from `legal_limits.csv`. SCR comes from S.23.01. Restricted Tier 1 remains indeterminate under the unresolved reporting-treatment evidence.

At a strict bound the largest source-precision multiple below it is `(ceil(bound / precision) − 1) × precision`. At an inclusive bound it is `floor(bound / precision) × precision`. A binding conclusion requires that reported eligible amount, supply exceeding the bound by more than one source unit, and sufficient evidence about the competing limit. Insufficient precision, overlapping restrictions and missing evidence produce an indeterminate conclusion. These rules assess attribution. The reported compliance field separately applies the exact mapped operator.

The `tier_changes` array records both statuses, direction, the change in the observed eligibility adjustment and the change in the attributed effect. An effect requiring an indeterminate period remains indeterminate with its citations. The Tier_limits worksheet recalculates the observations, conclusions and transitions from the raw period tabs.
