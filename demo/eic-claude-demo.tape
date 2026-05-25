# EIC + Claude Code — terminal demo
#
# Shows a full workflow: init workspace, ask Claude to add a postgres
# integration, configure the connection secret, then query via Claude.
#
# Run:  cd /Users/bsampera/Documents/bleak-dev/eic && vhs demo/eic-claude-demo.tape
# Out:  demo/eic-claude-demo.gif

Output demo/eic-claude-demo.gif

Require eic
Require uv

Set Shell "bash"
Set FontSize 15
Set FontFamily "JetBrains Mono,Menlo,monospace"
Set Width 1000
Set Height 600
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set Padding 20
Set WindowBar "Colorful"
Set WindowBarSize 40
Set BorderRadius 8
Set Framerate 24

# ═══════════════════════════════════════════════════
# Hidden prep — clean slate, cd into workspace, claude alias
# ═══════════════════════════════════════════════════
Hide
Type@1ms "rm -rf /tmp/eic-demo-ws"
Enter
Sleep 300ms
Type@1ms "mkdir -p /tmp/eic-demo-ws && cd /tmp/eic-demo-ws"
Enter
Sleep 300ms
Type@1ms "DEMO_DIR=/Users/bsampera/Documents/bleak-dev/eic/demo"
Enter
Sleep 200ms
Type@1ms "claude() { uv run --quiet python $DEMO_DIR/claude-sim.py add; }"
Enter
Sleep 200ms
Type@1ms "clear"
Enter
Sleep 200ms
Show

# ═══════════════════════════════════════════════════
# Scene 1: Init  (~5s)
# ═══════════════════════════════════════════════════
Sleep 1s

Type "eic init"
Enter
Sleep 3s

# ═══════════════════════════════════════════════════
# Scene 2: Ask Claude to add postgres  (~14s)
# ═══════════════════════════════════════════════════

Type "claude"
Enter
Sleep 13s

# ═══════════════════════════════════════════════════
# Hidden: switch claude alias to query mode
# ═══════════════════════════════════════════════════
Hide
Type@1ms "claude() { uv run --quiet python $DEMO_DIR/claude-sim.py query; }"
Enter
Sleep 200ms
Type@1ms "clear"
Enter
Sleep 200ms
Show

# ═══════════════════════════════════════════════════
# Scene 3: User follows Claude's instruction — adds PG_URL
# ═══════════════════════════════════════════════════
Sleep 1s

Type "echo 'PG_URL=postgresql://user:pass@db.example.com/myapp' >> .env"
Enter
Sleep 3s

# ═══════════════════════════════════════════════════
# Scene 4: Query postgres via Claude  (~12s)
# ═══════════════════════════════════════════════════

Type "claude"
Enter
Sleep 11s

Sleep 3s
