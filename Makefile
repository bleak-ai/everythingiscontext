# Dashboard + package build. The Python package itself needs no Makefile;
# these targets exist because the wheel embeds the built web app.

.PHONY: web-dev web-build build test

# Vite dev server on :5179, proxying /api to a running `gcontext up` (:4242
# by default; override with VITE_API=http://127.0.0.1:<port>).
web-dev:
	cd web && npm install && npm run dev

web-build:
	cd web && npm install && npm run build

# Wheel + sdist. web-build first: hatchling force-includes web/dist.
build: web-build
	uv build

test:
	uv run --group dev python -m pytest -q
