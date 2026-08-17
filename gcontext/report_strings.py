"""Every wording token of the code-built reports (docs/setup-script.md).

This module is the single source of truth for report wording: the setup
report (Block 1) and the explain report. Edit a string here, restart the
server, done. Strings only, no logic; layout (padding, wrapping,
alignment) stays in report.py. The tests import these constants, so a
wording change never breaks the suite.
"""

# Shared
HEADER = "Welcome to gcontext"
NO_AGENTS = "No agents installed."
AGENT_LABEL = "Agent:"

# Setup report (Block 1)
CONNECTIONS_HEADING = "Connections"
CONNECTION_OK = "OK"
CONNECTION_MISSING = "MISSING"
NO_KIND = "(no kind)"
STATUS_LABEL = "Status:"
STATUS_NEEDS_SETUP = "needs setup"
STATUS_CONNECTION_MISSING = "connection missing"
STATUS_READY = "ready"

# Install report (agent tool and `gcontext add`)
INSTALLED_DEPENDENCY_LINE = "Installed {name} ({count} files) at {path}/ (required by {required_by})."
CONNECTION_STUB_CREATED_LINE = (
    "Created connection stub connections/{kind}/ (declared by the module). "
    "Setup fills it in."
)
CONNECTION_MISSING_LINE = (
    "Connection {kind} is missing. The agent needs it; set one up manually."
)
CONNECTION_EXISTS_LINE = "Connection {kind} already exists; the agent uses it."

# Explain report
DOES_LABEL = "Does"
CONNECTS_LABEL = "Connects"
LEARNS_LABEL = "Learns"
FLOW_LABEL = "Flow"
FLOW_NOT_DECLARED = "not declared"
LAST_ACTIVITY_LABEL = "last activity"
FILES_WORD = "files"
UNKNOWN_AGENT = 'Unknown agent "{agent}". Installed agents: {ids}.'
NO_INSTALLED_IDS = "none"
