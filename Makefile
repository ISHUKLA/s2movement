.PHONY: setup check format

setup:
	uv sync --locked --group dev

check: export PYTHONDONTWRITEBYTECODE = 1
check: export PYTEST_DISABLE_PLUGIN_AUTOLOAD = 1
check:
	uv sync --check --locked --group dev --offline --no-cache --no-python-downloads
	.venv/bin/ruff check --no-cache src tests
	.venv/bin/ruff format --check --no-cache src tests
	.venv/bin/mypy --no-incremental --cache-dir=/dev/null src tests
	.venv/bin/python -B -m pytest -p no:cacheprovider -q

format:
	.venv/bin/ruff format --no-cache src tests
