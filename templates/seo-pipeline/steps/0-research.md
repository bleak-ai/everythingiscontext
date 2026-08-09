# Step 0: Research keywords

## Purpose

Pull raw keyword data from the connected source for the seed topic. Collect search volumes, difficulty scores, and related terms.

## Input

- `seed` parameter: the topic to research.
- The keyword-source connection: to query for keyword data.

## Output

`runs/{slug}/0-research.md` with:

- **Seed**: the seed as entered.
- **Source**: the keyword tool used.
- **Keywords**: a table of keywords found (keyword, monthly volume, difficulty, intent type).
- **Total count**: the number of keywords collected.

## How to execute

1. Query the keyword source for the seed term.
2. Expand with related keywords, questions, and long-tail variations.
3. For "narrow" scope, stay close to the seed. For "broad" scope, explore adjacent topics and variations.
4. Record all keywords with their metrics.
5. Present a summary to the user: top 10 by volume and top 10 by opportunity (high volume, low difficulty).

## Done when

The research file is written with at least 20 keywords (narrow) or 50 keywords (broad).
