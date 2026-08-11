Write or update a file in the project. Creates parent directories if needed.

Use this to update connection context docs, create playbooks, write logs, etc.
Cannot write to secrets.env: secret values never leave the user's machine.

Updating an existing file returns a unified diff of the change (capped at
200 lines), so every write is auditable in the transcript. Creating a file
returns its size and line count.

The result can carry a warning: an index.md that does not reference every
sibling, or a new file the folder's index.md does not mention. The write
still happens; update the index right away so the map stays complete.

Args:
    path: Relative path within the project (e.g. 'modules/support-agent/playbooks/refund.md')
    content: The full file content to write.
