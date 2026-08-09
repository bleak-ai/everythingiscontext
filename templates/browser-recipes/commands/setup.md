---
description: Connect your browser automation interface and verify access.
---

# Setup

Read this workflow's `index.md` and `steps/index.md` first to understand what browser-recipes does and what it needs.

## 1. Identify the browser automation

Ask the user which browser automation they have available: Chrome CDP, Playwright, Puppeteer, or another. Find the matching connection in the agent's environment, or help the user create one.

## 2. Verify access

Smoke test: open a simple URL (e.g. https://example.com) in the browser to confirm the connection works. Present what the browser sees (page title, visible text) as proof.

## 3. Report

If the smoke test passes, report setup complete. If it fails, diagnose and fix the connection before declaring done.

## What setup creates

Nothing. The `recipes/` folder and `runs/example/` ship with the template. Real recipes and real runs are created during use.
