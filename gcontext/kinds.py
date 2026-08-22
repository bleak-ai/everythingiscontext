"""Connection kinds: the fixed capability enum from docs/setup-script.md.

A `connections` entry in an agent manifest names a capability, not a
transport and not a product. This tuple is the single source for the kind
values in code; new kinds enter by editing it and the documented list in
docs/setup-script.md (between the kind-enum markers) in the same change.
tests/test_kinds_doc.py asserts the two stay equal. Other surfaces
(docs/connections.md, prompts/framework-instructions.md) point at the doc
with at most two examples instead of repeating the list.
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
    "scheduler",
)
