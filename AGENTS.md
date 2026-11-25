# Project context

This repository holds a local command-line tool for actuaries who sign off Solvency II reporting. It takes two consecutive annual reporting packages for one solo European life insurer on the Standard Formula and produces an Excel reconciliation workbook, a JSON summary, and optionally an LLM-drafted list of review questions. The requirements are in docs/spec.md. The original user story is in docs/user-story.md.

The person reading the output is a Head of Actuarial Function deciding whether to sign a regulatory submission. They will rely on a figure only if they can trace it to a reported cell. A missing number is acceptable to them; a plausible wrong number is not. The rules below follow from that.

## Rules for every task

- The deterministic core (ingestion, comparability gate, bridges, anomaly flags, Excel, JSON) makes no LLM calls and no network calls. A reviewer must be able to run it with the LLM off and get identical numbers every time.
- Every number in any output comes from the fact ledger and carries its citation in the form [Period | Template | Row | Col]. A calculated number carries the citations of its inputs.
- An Excel cell that shows a calculated value contains a formula that resolves back to the raw period tabs. Reviewers audit by following formulas, so a pasted value defeats the purpose.
- Every bridge shows opening, movements, an explicit residual line, and closing. The residual is displayed and is never folded into an "other" line.
- When an input is missing, the affected output says "Unavailable" and names the missing template. Nothing is omitted silently or shown as zero.
- Template, row and column codes come from the files in mappings/, which record their source. Do not supply a code from memory. If one is missing, add it from the official EIOPA source or stop and say what is missing.
- Monetary arithmetic uses Decimal, because float rounding is enough to break a one-unit tolerance.
- The packages in tests/fixtures and their expected values are the independent check on the tool. When a test fails, fix the code. If you believe an expected value is wrong, stop and show the arithmetic instead of changing it.

## Working agreement

- Before reporting a task as finished, run `make check` (once it exists) and report the actual result, including anything that failed or that you did not run.
- Keep docs/progress.md current: what is done, what is verified and how, what is open. The next session starts from that file.
- If the spec is ambiguous in a way that could change a reported number, stop and ask. For other choices, take the simpler option and record it in docs/decisions.md.
- Stay within the task you were given. Note unrelated problems in docs/progress.md instead of fixing them.

## Commands

- `make setup` creates the development environment from the lockfile.
- `make check` checks the lockfile, lint, formatting, types and tests.
- `make format` applies Ruff formatting.
