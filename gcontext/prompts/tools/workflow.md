Manage workflows from the registry: search, install, check for updates, and update.

Four actions:

- **search**: find workflows in the registry. Pass a query to filter by id,
  name, description, or tags; omit it to list all available workflows.
- **install**: install a workflow by id into modules/. Refuses if the module
  already exists. After install, run the setup command to personalize it.
- **check**: compare installed workflows against the registry. Reports which
  files changed upstream, which you modified locally, and which changed on
  both sides. Pass an id to check one, or omit it to check all.
- **update**: pull upstream changes into an installed workflow. Files you
  modified locally are kept. Files changed on both sides get the upstream
  version written as `<file>.new` next to your version; merge the two and
  delete the `.new` file. Your runs, insights, and personal state are
  never touched.

Args:
    action: one of "search", "install", "check", "update"
    id: workflow id (required for install and update, optional for check)
    query: substring filter (used only by search)
