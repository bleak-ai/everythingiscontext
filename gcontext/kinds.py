"""Connection kinds: the fixed capability enum from docs/setup-script.md.

A `connections` entry in an agent manifest names a capability, not a
transport and not a product. This tuple is the single source for the kind
values in code; new kinds enter by editing it (and the doc list it mirrors).
The kind list is also mirrored in prose in
prompts/framework-instructions.md (connections bullet); update that file
in the same change.
"""

CONNECTION_KINDS = (
    "ticket-tracker",
    "product-api",
    "keyword-source",
    "browser",
    "source-control",
    "package-registry",
    "deploy-target",
    "notification-sink",
)
