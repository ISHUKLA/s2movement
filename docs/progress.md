# Step 0.0 — repository scaffold

Complete. The repository contains the installable `s2movement` package, its locked development environment, one import test and the directory guides for later sessions.

| Verification | Result |
| --- | --- |
| `make setup`, then `make check` on CPython 3.12.14 | uv installed the locked environment. Ruff lint and formatting passed, strict mypy passed for two source files, and the import test passed. |
| Compare the working tree before and after `make check` | File paths, contents, modes, symlink targets and modification times matched, including the virtual environment. Git metadata was excluded. |
| Run `make check` in a temporary copy after changing the project version without updating its lockfile | The lock check failed before lint or tests. The lockfile kept its original contents. |
| Create dummy files in `private/` and `output/` | `git check-ignore -v` identified the matching rules and `git status --porcelain --untracked-files=all` listed neither file. Both were deleted. |
| Compare the starting documents with the supplied sources | The user story matches the supplied file byte for byte. The Step 0 standing instructions are preserved in `AGENTS.md` with the Commands section appended. |

**Next is Step 1.** Write `docs/spec.md` from the user story and review its open questions before starting the cell mappings.
