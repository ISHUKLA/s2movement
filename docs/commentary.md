# Optional Pre-Sign-Off Challenge Pack

## Invocation and boundary

`s2movement compare opening.xlsx closing.xlsx --output-dir output/` remains the offline default. `--challenge-pack` is the explicit opt-in that may send pre-submission figures to Anthropic. The chosen model is `claude-sonnet-4-6`, overridable with `--commentary-model`; `ANTHROPIC_API_KEY` is read only after all local preflight gates pass. The provider uses [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) through the Python SDK. The Word result is `pre-sign-off-challenge-pack.docx`; `challenge-pack-status.json` says delivered or withheld and why. The deterministic workbook and JSON are written first and are never modified by commentary.

The provider interface accepts the system prompt and a request object, then returns a typed `Draft`. Its only case-specific inputs are a projection of the just-written JSON summary: cited bridge-line evidence, deterministic flags and deterministic abstention tags. The separate repository catalogue supplies static review wording and internal checks. A request inspection test compares every projected value and citation with the JSON. The provider receives no input workbook, fact ledger, expected answer key or private file path.

## JSON contract and current status

The optional path requires `gate.status = pass`, `citation_validation.status = pass`, `flags` and `abstentions` lists. Each abstention needs an `id`, a `evidence_id` resolving to a cited numeric JSON entry, and `consistent_hypotheses`. This is a fail-closed contract; a missing field withholds the pack before any provider call. The current deterministic producer does **not** yet emit the citation-validation result, flags or abstention tags. It therefore withholds the pack for all current benchmark packages. Implementing R-022–R-024 and the D9 abstention decisions in deterministic JSON is required before a live R-034 run. Adding a dummy pass marker would defeat the evidence gate.

## Draft structure and evidence gates

The provider returns typed fact, triage-question, hypothesis, abstention and verification-check items. Facts may contain `{ref:evidence_id}` placeholders. The renderer inserts the matching JSON value and all its source coordinate citations in a marked Word run. The model cannot supply a value-citation pair. Questions, hypotheses and checks select entries from `prompts/catalogue.json` by id and name the flags they address. The renderer supplies labels, hypothesis wording, the internal artefact and the precise comparison. Repeated selections are shown once. A missing catalogue id or a check without an artefact and comparison withholds the pack.

Catalogue conditions are evaluated against the JSON before the provider request and again after the response. An entry whose required flag or reported condition is absent is not offered. The foreseeable-dividend entry requires an explicit reported condition showing a nonzero amount at either date; reported zero at both dates excludes it. Unknown conditions fail closed. Every material flag must match at least one applicable catalogue entry, and the renderer includes its artefact and comparison even if the model omits a check. Every deterministic abstention tag produces a cited movement and the exact sentence “Insufficient evidence in QRT snapshots to attribute this movement”, followed by the consistent hypotheses. A model-selected percentage split is rejected.

The number gate inspects model text before insertion and the Word paragraphs after rendering. It rejects unmarked numbers, currency amounts and percentages. The only exempt numeral patterns in ordinary text are an entire QRT template/row/column code (`S.23.01.01.01`, `R0540`, `C0010`), a date (`2025-12-31` or day/month/year), an `Article 82(3)` reference, or a tier category (`Tier 3`). A monetary or ratio number is allowed only in a renderer-marked evidence run. The gate also rejects a model-typed bracket citation and checks fact text for ungrounded causal wording such as “driven by”, “caused by” and “due to”. These word checks are backstops: the typed structure and repository catalogue carry the main constraint.

## Word length measurement

The renderer reserves space in the body for observed movements, triage questions, labelled hypotheses and concrete checks. Overflow goes in an appendix after a page break. The R-026 test creates many distinct material-style items, converts the Word file to PDF using LibreOffice, extracts each page with `pypdf`, and counts pages before the page containing “Appendix”. The measured body is one page in the current test and the appendix starts on the next page. The generated pages were also rendered to PNG and inspected for clipping, heading placement and the absence of an ornamental title rule. This is a layout test, not a live-model quality score.

## Release measurement still needed

The six benchmark packages and seven scored runs cannot receive a live pack until the deterministic JSON contract above is met and an Anthropic API key is configured. Withheld packs count as misses. After those prerequisites, compare the rendered packs with `expected.yaml` for the R-034 abstention opportunities, invented figures, unlabelled causal claims and false abstentions; record each run and the aggregate result without changing the frozen answer keys.
