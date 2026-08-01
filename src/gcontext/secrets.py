"""Secrets: names are public, values never enter the context window.

Values live in secrets.env at the project root, parsed here and injected as
env vars at run time. Anything returned to the agent goes through scrub().
"""

from pathlib import Path


def load(root: Path) -> dict[str, str]:
    env_file = root / "secrets.env"
    if not env_file.exists():
        return {}
    pairs = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            pairs[key.strip()] = value.strip()
    return pairs


def scrub(text: str, secrets: dict[str, str]) -> str:
    for value in secrets.values():
        if value and len(value) > 3:
            text = text.replace(value, "***")
    return text
