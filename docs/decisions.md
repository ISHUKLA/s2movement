# Step 0.0 tooling decisions

| Choice | Reason |
| --- | --- |
| Git on local `main` | Gives every later session a common starting commit. |
| CPython 3.12.14 | An exact patch pin in `.python-version` makes setup repeatable within the project's Python 3.12 requirement. |
| uv and a committed `uv.lock` | Reviewers install the same Python dependencies for their platform. `uv sync --locked` fails when the project and lockfile disagree. |
| `src/s2movement/` and the pinned `uv_build` backend | uv installs the package directly from the standard source layout. Pinning the build backend also fixes the version used for isolated builds. |
| A separate dev dependency group | pytest, Ruff and mypy are needed to develop the package. The runtime dependency list can stay empty. |
| pytest | A single import test exercises the package installed in the environment. |
| Ruff lint and format | One tool checks style, undefined names, import order, common bugs and Python 3.12 idioms. The separate formatting target applies its formatter. |
| Strict mypy | New package and test code must pass type checks from the first commit. |
| Make | Three targets give reviewers stable commands. The check target verifies the environment and lockfile offline, runs tools from the project environment and disables persistent caches and bytecode writes. |
| Git ignore rules | Restrict tracked private inputs, outputs and public downloads to the designated documentation and provenance files. Ignore local credentials, environments and caches. |
| CSV reference manifest | A header-only manifest reserves fields for filenames, source URLs, versions and SHA-256 digests. Step 2 supplies the entries. |
| Git attributes | Normalise text to LF and preserve Excel and ZIP files as binary. |
