# Release evidence report — 27 November 2026

**Release decision: fail; no v1.0 tag or public demo.** This is a measurement of the current handoff copy, not a change to the frozen benchmark. The seven scored runs cover the five named cases and six packages under R-031. The independent package manifest checksum was `eb073b5d400ad380d518bcb40ede0cd6e5ae5aa160d0f419bf76d8987e78a044` before scoring. No threshold, package, `expected.yaml`, or manifest was edited for this report.

## Commands and retained evidence

From the repository root `/Users/coralieroland/Documents/s2movement-handoff-2026-11-26`:

```text
PYTHONPATH=src .venv/bin/python -B tests/fixtures/bench_score.py > docs/release-evidence/benchmark-score.json 2> docs/release-evidence/benchmark-stderr.log
```

The scorer exited **1**, meaning its aggregate deterministic gate failed. The complete scored output is [`release-evidence/benchmark-score.json`](release-evidence/benchmark-score.json); its stderr is [`release-evidence/benchmark-stderr.log`](release-evidence/benchmark-stderr.log). The scorer recalculated each generated workbook with LibreOffice, compared the CLI JSON and workbook with the independent `expected.yaml` files, and verified the frozen manifest. The retained JSON includes every finding ID, not just the aggregates below.

The two new trial tool-output commands and their deliberately failing reconciliation exits are recorded in [`tests/trial/README.md`](../tests/trial/README.md). The final `make check` result for the repository is recorded in [`progress.md`](progress.md).

`make check` verified the unchanged frozen manifest, offline lockfile, Ruff, strict mypy and **367 passed in 414.32s**. Its complete output is [`release-evidence/make-check.log`](release-evidence/make-check.log). It does not use the diagnostic scorer as a release pass gate. A green `make check` cannot supersede the failed release metrics below.

## R-031–R-036 release gates

| Gate | Measured value | Threshold or required outcome | Result and evidence |
| --- | --- | --- | --- |
| **R-031** benchmark cases | 5 named cases, 6 packages, 7 scored runs. Gate outcomes 7/7; scale stop 1/1; unavailable lines 16/16. Only 1/7 scored flag sets matched; 35 expected cross-template checks remain open. Case 4's required abstention was not delivered and case 5's tier conclusions missed. | Every named scenario must exhibit its specified stop, conversion tie, warning, unavailable detail, abstention, and eligibility/tax effects. | **Fail.** Frozen scorer command above; `metrics`, `findings`, and `open_benchmark_dependencies` in `benchmark-score.json`. |
| **R-032** supported bridges and signs | 53/53 supported bridges tied; 0 sign inversions; expected stop 1/1; unavailable 16/16; withheld 1/1. No scored supported bridge omission was reported. | 100% ties, exact ratio decomposition, zero sign inversions, all expected stop/unavailable outcomes, no expected supported bridge omitted. | **Pass for the scored bridge outcomes.** Same command/file, `bridges_tied`, `sign_inversions`, `stops`, `unavailable`, `withheld`. This does not clear the other gates or the 35 open check dependencies. |
| **R-033** values and citations | 3,276/4,045 expected numeric values = **80.99%**; 7,867/9,808 citations = **80.21%**. The runner records 769 citation errors and 769 wrong/missing values, with 1,091 unsupported-number findings. | 100% expected numeric values and 100% source-coordinate validation, including recalculated values. | **Fail.** Same command/file, `numeric_values`, `citations`, `findings`. |
| **R-034** commentary | **0/20** independently seeded ambiguous movement opportunities received a delivered abstention; recall **0%**. No benchmark pack was delivered, so fabricated-number and unlabelled-causal-claim rates are **not measurable**, not zero. | At least 95% recall; zero fabricated numbers and zero unlabelled causal claims. Missing packs count as misses. | **Fail.** The 20 opportunities are the five nonblocked `expected.yaml` runs with four abstentions each; no current JSON abstention tags or validated R-022 result enable delivery. Same scorer command/file reports `R-034: not yet measured`; the 0/20 delivery count is from those frozen keys and the absence of packs. No live provider call was made. |
| **R-035** reviewer utility | **Open:** 0/8 practising reviewers have completed the paired trial. No times, detection counts or owner sign-off exist. A trial kit has been prepared. | Median of eight paired time reductions ≥35%; tool detection rate ≥Excel separately for cross-template and comparability defects; owner sign-off. | **Open, not a pass.** Protocol and materials in [`tests/trial/README.md`](../tests/trial/README.md), assignment and formula workbook in `tests/trial/coordinator/`. No human-trial command or observed output exists yet. |
| **R-036** release authorization | R-031, R-033 and R-034 fail; R-035 remains open. No owner-approved trial outcome or v1.0 release decision. | Recorded passes for R-031–R-035 and owner sign-off before either v1.0 tag or public demo. | **Fail.** The gate results above and the blank [`trial sign-off`](../tests/trial/coordinator/SIGNOFF.md). |

**Additional diagnostic measures:** consistency comparisons 73/96 (76.04%); tier assessments 0/72 (0%); scored flag sets 1/7 (14.29%). The runner reports **zero false abstentions**. That count is information only: the spec has no false-abstention threshold, and zero reflects that the current output does not tag ambiguous movements at all. It must not be read as good commentary performance.

## Trial kit and limitations

The separate [`trial kit`](../tests/trial/README.md) contains two newly generated fictional cases A and B, a plain Excel cell diff and deterministic tool workbook/JSON for each, the identical reviewer task, balanced eight-reviewer assignment, blind adjudication file, timing/detection formulas, private answer key, and owner sign-off form. Its builder imports the independent fixture builder and no tool code. Both cases have the same 608 populated coordinates per period and one EUR 6 million cross-template SCR discrepancy plus the same VA comparability change; the SCR break is at closing in A and opening in B. The answer key and matching rationale are in the kit. The tool CLI exits 1 on both cases because the seeded SCR reconciliation fails, while still writing workbook and JSON. The kit uses the **workbook and JSON only** option: the challenge pack cannot currently be released.

The kit's separate `tests/trial/SHA256SUMS` fixes the 17 case, output, key and scoring-template files before recruitment. It is distinct from the owner-approved frozen benchmark manifest.

The trial is prospective. The two cases have matched construction, but actual human difficulty and the R-035 utility numbers can only be established by the eight practising actuaries under the D9 crossover. The scorer must classify anonymized first issue lists with method labels removed, then the coordinator reveals assignments and calculates the rates. The answer key is withheld from reviewers and no feedback is given between runs.

Recruitment should wait until the automated gates pass. Current tool outputs are preserved as a kit prototype; a repaired build must regenerate them from the same A/B sources and record a revised trial checksum before reviewers see them.

## Requirements not implemented or not verified for release

| Requirement IDs | Remaining work or evidence gap |
| --- | --- |
| **R-001** | XBRL instance input and workbook/XBRL cell-for-cell equivalence remain unimplemented. The adapter deliberately refuses `.xbrl` and mixed pairs because 484/1,176 benchmark facts lack the full metric/dimension mapping; see `docs/progress.md`. |
| **R-004, R-008** | The mapping is still preliminary for several metadata locations, signs, subtotal relationships and like-for-like scopes. The benchmark matched only 73/96 consistency comparisons; 35 source-evidence dependencies remain open. |
| **R-009** | Prior isolated repeatability and no-network tests passed in `make check`, but this report did not rerun the full seven-run benchmark twice under network isolation. The full-benchmark R-009 claim is therefore unverified. |
| **R-012–R-021** | Individual bridge tests and 53/53 scored bridge ties exist. The 769 wrong/missing expected values are concentrated in tier limits (480), flags (271) and tier changes (18); there are also 55 unsupported bridge numbers among 1,091 unsupported output numbers. R-017–R-018 tier attribution cannot be released while its source treatment remains unresolved. R-012–R-016 and R-019–R-021 still need complete source/citation validation before a release claim. |
| **R-022** | The final source/citation validator is not implemented for every output path. Citation accuracy is 80.21%, not 100%; the mutation validations required by R-022 remain open. |
| **R-023–R-024** | The declarative rule engine and configurable threshold overrides are not complete. Only 1/7 scored flag sets matched; boundary/mutation coverage and deterministic abstention tags remain open. |
| **R-025–R-030, R-037** | An optional offline-tested Anthropic commentary prototype exists, but all current benchmark packs withhold before a provider call because R-022 validation, rule flags and abstention tags are absent. No live six-package run was possible without an API key. The required Word pack, contradiction filtering, numerical safety and concrete checks are not verified across the frozen benchmark. |
| **R-031, R-033–R-036** | The measured failures and open human trial above block release. R-032 alone meets its scored bridge threshold. |

The Step 2 evidence record in [`mappings/VERIFICATION.md`](../mappings/VERIFICATION.md) still labels the cell audit and some legal/reporting treatments unverified. In particular, the restricted Tier 1 excess treatment cannot be independently inferred from S.23.01; the frozen candidate expects an attribution that the sourced record does not yet justify. Its owner-approved manifest has therefore not been changed. No unsupported legal or cell reading has been substituted for that gap.
