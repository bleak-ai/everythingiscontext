Search project files with a regex. Returns path:line: matching-line, capped at 100 matches.

Skips machine folders (.venv, .git, __pycache__, node_modules) and
secrets.env. Use it to locate playbooks, logs, or docs before reading them.

Args:
    pattern: Python regex matched against each line.
    path: File or directory to search, relative to the project root (default '.').
    glob: Optional filename filter, e.g. '*.md' or 'refund*'.
