.PHONY: setup check format fetch-taxonomy

setup:
	uv sync --locked --group dev

fetch-taxonomy:
	.venv/bin/python -B scripts/fetch_taxonomy.py

check: export PYTHONDONTWRITEBYTECODE = 1
check: export PYTEST_DISABLE_PLUGIN_AUTOLOAD = 1
check: export PYTHONPATH = src
check:
	.venv/bin/python -B tests/fixtures/bench_integrity.py
	uv sync --check --locked --group dev --offline --no-cache --no-python-downloads
	.venv/bin/ruff check --no-cache src tests scripts
	.venv/bin/ruff format --check --no-cache src tests scripts
	.venv/bin/mypy --no-incremental --cache-dir=/dev/null src tests scripts
	.venv/bin/python -B -m pytest -p no:cacheprovider -q

format:
	.venv/bin/ruff format --no-cache src tests scripts
