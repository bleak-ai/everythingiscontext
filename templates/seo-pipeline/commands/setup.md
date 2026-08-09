---
description: Connect your keyword research source and verify access.
---

# Setup

Read this workflow's `index.md` and `steps/index.md` first to understand what the SEO pipeline does and what it needs.

## 1. Connect the keyword source

Ask the user which keyword research tool they use (Google Search Console, Ahrefs, Semrush, Ubersuggest, or another). Find the matching connection in the agent's environment, or help the user create one.

## 2. Understand the user's site

Ask the user about their site or niche. This context is necessary for intent matching in step 2 (evaluate). Record a short summary of the site's topic and audience in this workflow's `index.md` body or a config note.

## 3. Smoke test

Query the keyword source for a simple term related to the user's main topic. Present the top 5 results as proof that the connection works.

If the smoke test passes, report setup complete. If it fails, diagnose and fix the connection before declaring done.

## What setup creates

- A verified keyword-source connection.
- A note about the user's site context for intent matching.
- Nothing else. The `insights/` folder and `runs/example/` ship with the template. Real runs are created during use.
