.PHONY: build test serve

build:
	uv build

test:
	uv run -m pytest

serve:
	uv run gcontext serve .
