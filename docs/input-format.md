# Normalized workbook input format

**Owner approved; adapter implemented for the first slice.** This format describes one reporting period per `.xlsx` file. It is an input contract, not an official EIOPA template and not a claim that a workbook contains all disclosures. The full design and first-slice limits are in [architecture.md](architecture.md). XBRL, when implemented later, fills the same ledger directly and does not have to mimic this workbook.

## Workbook structure

Use `Metadata` and `Contexts` sheets and one sheet for each supplied template family, named exactly as the family, such as `S.02.01` or `S.23.01`. Omit an unavailable template sheet; a missing sheet or missing cell is not zero. Sheet order has no significance. Cell values are literals, not formulas or external links. Macros, formulas, error-valued cells and external workbook links are rejected rather than silently evaluated. Blank monetary cells are unreported, whereas numeric `0` is a reported zero.

In template sheets, records are laid out in one or more **blocks**. A block identifies the full EIOPA table and a context, then uses the actual row codes as row labels and column codes as column headings. Multiple physical tables or contexts for the same family use separate blocks in the same sheet. Thus one template sheet can contain the two S.23.01 tables without losing the full table identity. Blocks must not overlap. A duplicate full table/row/column/context is an error, even when the values happen to agree.

## Metadata sheet

Column A is the exact field name and B is the declared value. For this draft the rows below are fixed, making the actual header location unambiguous. An assertion in this sheet is cited as that workbook cell. Column C optionally describes an upstream original-source location; it does not replace the `Metadata` cell locator. If S.01.02 cells are also supplied, the adapter keeps both pieces of evidence and rejects a conflict instead of silently selecting one.

| Row | A: field | B: value or allowed values |
| --- | --- | --- |
| 1 | `field` | `value` |
| 2 | `format_version` | `0.1` |
| 3 | `reference_date` | ISO date, e.g. `2024-12-31` |
| 4 | `variant` | `supervisory` or `public_disclosure` |
| 5 | `taxonomy_version` | `2.8.2` for v1 |
| 6 | `taxonomy_variant` | `base`, `nace_2_1_hotfix` or `unknown`; record the actual evidence, not an inference from a shared schema reference |
| 7 | `perimeter` | `solo`, `group` or `unknown` |
| 8 | `frequency` | `annual`, `quarterly` or `unknown` |
| 9 | `lei` | Undertaking LEI as text |
| 10 | `undertaking_name` | Legal name as text |
| 11 | `currency` | ISO 4217 code, e.g. `EUR` |
| 12 | `money_unit_scale` | Positive integer multiplier from a displayed reporting unit to one currency unit: `1` for euros, `1000` for thousands of euros |
| 13 | `money_precision` | Smallest reported step in **displayed reporting units**, e.g. `1`; independent of the scale multiplier |
| 14 | `scr_method` | `standard_formula`, `partial_internal_model`, `full_internal_model` or `unknown` |
| 15 | `rff_indicator` | `yes`, `no` or `unknown` |
| 16 | `map_indicator` | `yes`, `no` or `unknown` |
| 17 | `ma_applied` | `yes`, `no` or `unknown` |
| 18 | `va_applied` | `yes`, `no` or `unknown` |
| 19 | `tmir_applied` | `yes`, `no` or `unknown` |
| 20 | `tmtp_applied` | `yes`, `no` or `unknown` |
| 21 | `ratio_precision` | Smallest reported step in ratio units, e.g. `0.0001`; `unknown` if not evidenced |

The RFF and MAP indicators and the MA/LTG/transitional flags are separate declarations; this format does not assume that an MA flag proves a MAP indicator. `unknown` is not `no`. The actual cited location and supporting evidence govern whether a gate can pass or must remain indeterminate/blocked. Additional source-specific facts can be added through template sheets; the schema does not create a fictitious EIOPA code for a workbook header.

The first-slice monetary calculation supports whole reporting-unit values with `money_precision` of `1`, and integral conversions to a common unit subject to the absolute integer bound in the architecture. Input amounts outside that subset fail explicitly. A later version may add per-cell unit/precision overrides, but cannot infer them from Excel display formatting. Ratio values use ratio units (`1.8` means 180%, not `180`). The declared ratio precision, not the number of lexical digits or the cell's display format, controls the D3 ratio check.

## Contexts sheet

Row 1 contains `context_id`, `entity_lei`, `reference_date`, `dimensions` in columns A–D. Each later row is a context declaration. `context_id` is a nonempty workbook-local identifier; entity and date must agree with the period metadata unless an explicitly documented mapping permits otherwise. `dimensions` is a JSON object, with `{}` for no explicit dimensions, and must be preserved in canonical sorted form. Keys are the DPM dimension identifiers and values are member identifiers, exactly as represented in `cells.csv.data_point_signature`; for example, `{"s2c_VG":"s2c_x80","s2c_BL":"s2c_x91"}`. Do not replace codes with display labels. Duplicate IDs or inconsistent context contents are errors. A later XBRL adapter maps the instance's QName dimensions and members into these canonical DPM codes and retains the original QNames in its source locator.

An empty dimension object is not by itself proof that a table requiring a Z/context selection represents the whole undertaking. The selected mapping must establish that meaning. An unresolvable or ambiguous context blocks the dependent comparison rather than choosing a row arbitrarily.

## Template blocks

Each block starts at column A and consists of:

1. `A`: `table`; `B`: the complete physical table code from the selected mapping.
2. On the next row, `A`: `context`; `B`: a `context_id` from `Contexts`.
3. An optional row has `A`: `coordinate_context`; `B`: the mapped coordinate context such as `Z0001`. This preserves source-table context where the mapping records it; it is not automatically an XBRL dimension.
4. On the next row, `A`: `row/column`; from B rightward, unique EIOPA column codes such as `C0010`.
5. Subsequent rows have a unique row code in A and reported literal values at their row/column intersections. An empty row ends the block. A subsequent block can begin on the next row.

Codes, variants and reportable cells must exist in `mappings/<taxonomy-version>/cells.csv` with the right table and context. A mapped but unverified sign, subtotal or relationship cannot be used in a calculation until the necessary evidence is checked. The physical workbook address of every populated intersection is retained as the source locator. Text entries that resemble formulas remain text; formula cells are rejected.

### Example contexts for the slice

The slice's normalized S.02.01 blocks use explicit DPM members, not an assumed “solo” context:

| Block | Table and rows | Context dimensions |
| --- | --- | --- |
| Investments excluding linked assets | `S.02.01.01.01`, R0070/C0010 | `s2c_VG` = `s2c_x80`; `s2c_BL` = `s2c_x91` |
| Linked assets | `S.02.01.01.01`, R0220/C0010 | `s2c_VG` = `s2c_x80`; `s2c_BL` = `s2c_x119` |
| Whole balance-sheet figures | `S.02.01.01.01`, R0500, R0900 and R1000/C0010 | `s2c_VG` = `s2c_x80`; no BL dimension |
| Reconciliation reserve excess | `S.23.01.01.02`, R0700/C0060 | `s2c_VG` = `s2c_x80`; `coordinate_context=Z0001` |

The DPM dictionary labels `s2c_BL:s2c_x91` “Neither unit-linked nor index-linked” and `s2c_BL:s2c_x119` “Unit-linked or index-linked”; `s2c_VG:s2c_x80` means “Solvency II value”. In XBRL these correspond to dimensions `s2c_dim:BL` and `s2c_dim:VG`, with member QNames in the mapped DPM domains. These dimensions distinguish facts which the four-part coordinate alone would merge. Their sources are cited in [VERIFICATION.md](../mappings/VERIFICATION.md#2--like-for-like-overlaps).

A block repeats its physical table when a row needs a different context. For example, the R0070 block cannot share the R0220 context, and neither can share the whole-balance-sheet context. The row-cell locator is the actual workbook location (such as `S.02.01!B7`) plus the input file identifier and hash; it is never the corresponding address in an official EIOPA workbook. Other tables can be represented by further blocks. The gate selects the declared supervisory or public physical tables. A public comparison with unresolved operand or context equivalence is labeled indeterminate.

## Validation and corrections

Parse decimal text exactly; accept Excel numeric literals only when their stored value can be represented without loss under the stated slice boundary. Reject NaN, infinity, unknown table codes, duplicate headers/rows, formulas, conflicting evidence and incompatible or unexplained contexts. Do not use cell appearance to infer a unit, precision or missing value.

A metadata correction is supplied with `--corrections corrections.json`; a scale conversion is supplied with `--confirmations confirmations.json`. Both files use UTF-8 JSON and `schema_version: "0.1"`. A correction item names `period`, `file_id`, `field`, `original_value`, `corrected_value`, `reason`, `reviewer` and `evidence`; the original value must match the cited workbook metadata. A correction to `lei` or `reference_date` must also agree with every workbook context. A confirmation item names `period`, `file_id`, `factor`, `target_unit_scale`, `reason`, `reviewer` and `evidence`; in this slice the factor must convert the declared source scale to currency units. The original workbook and source values remain unchanged. Both the source value and correction/conversion record, reason, factor, resulting unit and rerun gate result are recorded in the outputs. Acknowledgement alone is not a correction or conversion. Missing required evidence is a hard stop where D2 requires it; unsupported detail is reported as unavailable or indeterminate with its cause.


## Gate behavior for normalized workbooks

Supply either period first. The summary records the chronological order and whether the pair was reversed. Equal dates and gaps other than a successive annual date produce a stop with the two cited dates. The anniversary rule preserves the month and day, and accepts adjacent February month ends across a leap year. The gate reports any PDF input at its file locator. A pair with a hard stop produces a dashboard and JSON with an empty bridge list.

Use a verified `taxonomy_variant` of `base` or `nace_2_1_hotfix` for a revision comparison. The release remains 2.8.2. A normalized S.01.01 filing inventory may use `reported` for an affirmative declaration and `not reported` for a negative one. Supply actual financial template blocks for the amounts to be checked. S.01.02 declarations corroborate the header at their own physical cells. If the declarations conflict, the gate reports both locations.

For a supervisory S.25.01 undertaking SCR comparison, the normalized table uses Z0010 with `{"s2c_AO":"s2c_x0"}` for the Article 112 selection. An SR block that demonstrates an active RFF or MAP must include its matching portfolio member and fund identifier in the referenced context. Keep different portfolios in separate contexts and blocks. The [verification supplement](../mappings/VERIFICATION.md#step-5-evidence-supplement--r-008) identifies the evidence.

The [R-008 catalogue](../mappings/2.8.2/consistency.json) lists each equation, required context, D3 tolerance, dependency and verification status. Each monetary comparison uses the reporting unit applicable to that comparison. A confirmed conversion preserves its coarser precision. The reported ratio is compared with the exact quotient. An unknown ratio precision gives an indeterminate result. A failure withholds the listed dependencies and leaves independent movements usable.
