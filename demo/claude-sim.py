"""Simulates Claude Code responding in an EIC workspace.

Two modes:
  add   — Claude creates a postgres integration
  query — Claude queries postgres and returns signup stats

The script prints both the user's prompt (> ...) and Claude's
streamed response, mimicking Claude Code's interactive terminal.

Used by eic-claude-demo.tape.
Run: uv run --quiet python claude-sim.py <mode>
"""

import sys
import time


def typewrite(text, delay=0.02):
    """Print text character by character to simulate streaming output."""
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def scene_add():
    print()

    # User prompt — short and direct
    typewrite("\x1b[1;36m>\x1b[0m Add a postgres integration", 0.030)
    print()
    time.sleep(0.6)

    # Tool use — reading context
    typewrite("  \x1b[90mReading context/llms.txt \u2026\x1b[0m", 0.012)
    time.sleep(0.4)
    typewrite("    \x1b[90m\u2192 No existing postgres module\x1b[0m", 0.012)
    print()
    time.sleep(0.3)

    # Response
    typewrite("  I'll create a postgres integration for your workspace.", 0.020)
    print()
    time.sleep(0.3)

    # Tool use — creating module
    typewrite("    eic new integration postgres  \x1b[32m\u2713\x1b[0m", 0.012)
    time.sleep(0.2)
    typewrite(
        "    Write modules-repo/postgres/info.md  \x1b[32m\u2713\x1b[0m", 0.012
    )
    time.sleep(0.2)
    typewrite("    eic load postgres  \x1b[32m\u2713\x1b[0m", 0.012)
    print()
    time.sleep(0.4)

    typewrite("  Module ready. To connect, add your connection string", 0.020)
    typewrite("  to \x1b[1m.env\x1b[0m:", 0.020)
    print()
    typewrite(
        "    \x1b[90mPG_URL=postgresql://user:pass@host/dbname\x1b[0m", 0.015
    )
    print()
    time.sleep(0.3)

    typewrite(
        "  \x1b[33m\u2192\x1b[0m I'll use \x1b[1mPG_URL\x1b[0m for all database queries.",
        0.022,
    )
    print()


def scene_query():
    print()

    # User prompt
    typewrite(
        "\x1b[1;36m>\x1b[0m How many users signed up this week?", 0.030
    )
    print()
    time.sleep(0.6)

    # Tool use — reading context
    typewrite("  \x1b[90mReading context/llms.txt \u2026\x1b[0m", 0.012)
    time.sleep(0.3)
    typewrite(
        "    \x1b[90m\u2192 postgres integration loaded\x1b[0m", 0.012
    )
    time.sleep(0.3)
    typewrite("  \x1b[90mReading postgres/info.md \u2026\x1b[0m", 0.012)
    time.sleep(0.3)
    typewrite(
        "    \x1b[90m\u2192 Connection:\x1b[0m PG_URL  \x1b[32m\u2713\x1b[0m",
        0.012,
    )
    print()
    time.sleep(0.4)

    # SQL query
    typewrite("  \x1b[90mSELECT count(*) FROM users\x1b[0m", 0.015)
    typewrite(
        "  \x1b[90mWHERE created_at >= now() - interval '7 days';\x1b[0m", 0.015
    )
    print()
    time.sleep(0.5)

    # Result
    typewrite("  \x1b[1m47 new users signed up this week.\x1b[0m", 0.022)
    print()
    time.sleep(0.3)

    typewrite("  Breakdown by plan:", 0.018)
    typewrite("    \x1b[1m\u2022\x1b[0m Free:        31", 0.015)
    typewrite("    \x1b[1m\u2022\x1b[0m Pro:         12", 0.015)
    typewrite("    \x1b[1m\u2022\x1b[0m Enterprise:   4", 0.015)
    print()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "add"
    if mode == "add":
        scene_add()
    elif mode == "query":
        scene_query()
