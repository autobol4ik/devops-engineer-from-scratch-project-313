.PHONY: install run dev test lint

FRAMEWORK ?= flask

install:
	uv sync
	npm ci

run:
	uv run flask --app main run --host 0.0.0.0 --port 8080

dev:
ifeq ($(FRAMEWORK),flask)
	npm run dev
else
	@echo "Unsupported framework. Expected: flask" >&2
	@false
endif

test:
	uv run pytest

lint:
	uv run ruff check .
