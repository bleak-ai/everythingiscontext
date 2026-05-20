# example

## Purpose
This is a sample module showing the structure of a context module. Use it as a reference when creating your own modules.

## Where it lives
This module exists locally in your workspace.

## Auth & access
No authentication needed — this is a documentation-only module.

## Key entities
- **Modules** — folders with a `module.yaml` and `llms.txt`
- **Kinds** — integration, task, or workflow

## Operations
- Read this module's files to understand the structure
- Create your own module with `python eic.py new integration <name>`

## Examples
```bash
# Create a new integration module
python eic.py new integration stripe

# Load it into the workspace
python eic.py load stripe

# Check module structure
python eic.py validate stripe
```
