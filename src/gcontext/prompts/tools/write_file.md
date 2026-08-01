Write or update a file in the project. Creates parent directories if needed.

Use this to update connection context docs, create playbooks, write logs, etc.
Cannot write to secrets.env or connection.yaml files.

Args:
    path: Relative path within the project (e.g. 'modules/support-workflow/playbooks/refund.md')
    content: The full file content to write.
