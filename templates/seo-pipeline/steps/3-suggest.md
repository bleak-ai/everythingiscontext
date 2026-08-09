# Step 3: Suggest content ideas

## Purpose

Turn the evaluated clusters into a prioritized list of concrete content ideas. Each idea has a target keyword, a working title, and a format suggestion.

## Input

- The evaluated clusters from step 2.

## Output

`runs/{slug}/3-suggestions.md` with a prioritized list. For each suggestion:

- **Target keyword(s)**: the primary and secondary keywords.
- **Working title**: a draft title for the content piece.
- **Format**: the suggested content type (guide, list post, comparison, tool page, landing page, etc.).
- **Estimated difficulty**: from the keyword data.
- **Angle**: one sentence on the approach.

Also `runs/{slug}/done/info.md` to close the run.

## How to execute

1. Focus on A-rated clusters first, then B. Skip C-rated clusters.
2. For each cluster, propose 1-3 content ideas.
3. Each idea should target specific keywords from the cluster.
4. Suggest the format that best serves the intent: informational queries get guides, commercial queries get comparisons, transactional queries get landing pages.
5. For "narrow" scope, aim for 5-10 suggestions. For "broad" scope, aim for 15-30.
6. Write the suggestions file and the `done/info.md`.
7. Update `insights/index.md` with any new findings (e.g. "topic X is saturated as of this date", "niche Y has low competition").

## Done when

The suggestions file and `done/info.md` are written. `insights/index.md` is updated if new findings emerged.
