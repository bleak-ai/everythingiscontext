# Step 2: Evaluate opportunities

## Purpose

Score each cluster by opportunity. Opportunity combines volume (how many people search), difficulty (how hard to rank), and intent match (how well the user's site can serve the intent).

## Input

- The clusters from step 1.
- Any relevant entries from `insights/`.

## Output

`runs/{slug}/2-evaluation.md` with:

- Each cluster scored on volume (high/medium/low), difficulty (high/medium/low), intent match (strong/moderate/weak), and an overall opportunity rating (A/B/C).
- A one-line rationale for each rating.

## How to execute

1. For each cluster, assess volume from the keyword data.
2. Assess difficulty from the keyword difficulty scores.
3. Assess intent match by comparing what the user's site offers with what searchers want. Ask the user if unclear.
4. Check `insights/` for past findings about similar topics.
5. Rate each cluster: A (high opportunity, pursue first), B (moderate, worth considering), or C (low opportunity or too competitive).
6. Present the evaluation to the user.

## Done when

All clusters are scored and the user has reviewed the evaluation.
