# s2movement

s2movement reconciles two consecutive annual Solvency II filings for a solo life insurer using the Standard Formula. The local CLI reads normalized workbooks, orders and checks both filings, and writes an Excel review workbook and a cited JSON summary. The workbook includes balance-sheet, technical-provision, own-funds, SCR and solvency-ratio bridges. Run `make setup` to create the locked environment and `make check` to verify the benchmark manifest and run the checks and tests. Use `s2movement compare first.xlsx second.xlsx --output-dir output/` from the project environment. **Real reporting packages belong in `private/` and must never be committed.**

Review the [normalized input format](docs/input-format.md), [consistency equations](mappings/2.8.2/consistency.json) and [benchmark instructions](tests/fixtures/README.md).

`--challenge-pack` is an explicit Anthropic opt-in that would transmit cited pre-submission figures. It currently withholds the Word pack because the deterministic JSON has not yet completed its citation-validation, flag and abstention fields; see [the commentary contract](docs/commentary.md). The default command makes no model call.
