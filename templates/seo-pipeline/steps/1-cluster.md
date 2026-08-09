# Step 1: Cluster keywords

## Purpose

Group the raw keywords into topic clusters by search intent and semantic similarity. Each cluster represents one potential content piece or content hub.

## Input

- The keyword list from step 0.

## Output

`runs/{slug}/1-clusters.md` with:

- **Clusters**: a list of clusters, each with a name, the keywords it contains, the dominant intent (informational, transactional, navigational, commercial), and the aggregate monthly volume.

## How to execute

1. Group keywords by topic similarity and intent.
2. Each cluster should have a clear, single topic that one piece of content could address.
3. For "narrow" scope, expect 3-8 clusters. For "broad" scope, expect 8-20 clusters.
4. Check `insights/` for any notes on these topics from previous runs.
5. Present the clusters to the user for review.

## Done when

The clusters file is written and the user confirmed the grouping makes sense.
