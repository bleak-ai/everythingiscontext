---
id: seo-pipeline
name: SEO Content Pipeline
description: >
  Research keywords, discover content opportunities, and build a prioritized
  list of content ideas. Each run explores a seed topic and produces actionable
  suggestions, not finished articles.
parameters:
  - name: seed
    description: The topic or niche to explore (e.g. "BJJ gyms in Barcelona" or just "BJJ")
    required: true
  - name: scope
    description: '"narrow" for a focused list around one niche, "broad" for cluster discovery across the seed topic'
    required: true
connections:
  - kind: keyword-source
    description: A keyword research tool or data source (Google Search Console, Ahrefs, Semrush, or similar)
tags: [seo, content]
---

Research keywords for a seed topic, cluster them by intent, evaluate opportunities, and produce a prioritized list of content ideas. Each run delivers suggestions for what to build, not finished content.

The two parameters control every run:

- **seed**: the topic to explore. It can be broad ("BJJ") or specific ("BJJ gyms in Barcelona"). The agent uses it as the starting query against the keyword source.
- **scope**: controls how wide the research goes. "narrow" stays close to the seed and produces a focused list (3-8 clusters, 5-10 suggestions). "broad" explores adjacent topics and variations (8-20 clusters, 15-30 suggestions).

Run folders are named with a kebab-case slug derived from the seed: `{slug}` (e.g. `home-gym-equipment`, `bjj-gyms-barcelona`). The agent derives the slug during the research step.

## How it learns

The workflow accumulates cross-run findings in `insights/`:

1. **Insights** (`insights/index.md`): dated entries about keyword landscapes. Step 2 (evaluate) reads them before scoring clusters. Step 3 (suggest) updates them with new findings. Over time, insights help the agent avoid saturated niches and spot recurring opportunities.

2. **Run history** (`runs/`): every completed pipeline is a structured folder with research data, clusters, evaluation, and suggestions. The agent can search past runs to see how similar topics were handled.

## Narrow vs broad

Use "narrow" when you already know the niche and want a short, focused list of content ideas. The agent stays close to the seed and filters aggressively.

Use "broad" when you want to explore a topic space and discover clusters you had not considered. The agent expands the seed into adjacent areas and maps the full landscape before narrowing down.
