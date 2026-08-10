---
description: Browse, install, and update workflows from the registry
parameters:
  - name: name
    description: Workflow name to install or update (leave empty to browse all)
    required: false
---
You are managing workflows for this agent. Workflows are reusable procedures
with steps, runs, and commands that live in modules/.

If "$name" is provided, skip the overview and go straight to that workflow:
check if it is installed, offer to install or update it.

If "$name" is empty, show the full overview.

## Overview

1. Call list_dir("modules") to see what is installed locally.
2. For each module that has a `.template.yaml` (read it by path), note it as
   a registry-installed workflow.
3. Call the `workflow` tool with action="search" to get the full registry list.
4. Call the `workflow` tool with action="check" (no id) to get update status
   for all tracked workflows.
5. Present one merged list to the user. For each registry workflow, show:
   - Name, one-line description, tags
   - Status: "installed, up to date", "installed, update available", or
     "not installed"
   For local modules without a `.template.yaml`, show them in a short
   "Local (not from registry)" section at the end.
6. End with: "Say a workflow name to install or update it."

## Install

When the user picks a workflow that is not installed:

1. Call the `workflow` tool with action="install" and the workflow id.
2. Tell the user it is installed and suggest running the setup command:
   "Run /mcp__<agent>__<workflow-id>__setup to personalize it."

## Update

When the user picks a workflow that is installed and has updates:

1. Call the `workflow` tool with action="update" and the workflow id.
2. If there are conflicts (.new files), read both versions and help the user
   merge them. Delete the .new file after merging.
3. Report what changed.

## Already up to date

When the user picks a workflow that is installed and current, say so and
offer to run it instead: "It is up to date. Run /mcp__<agent>__<workflow-id>__run
to start a new run."
