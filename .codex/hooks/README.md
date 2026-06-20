# Yasi Server Startup Hooks

This directory contains project-local Codex hooks for preventing foreground
long-running server commands from blocking Codex shell execution.

## Installed Hooks

- `SessionStart`: adds the server startup policy as extra developer context on
  `startup`, `resume`, and `compact`.
- `PreToolUse`: inspects shell-like tool input and denies high-confidence
  foreground or unsafe local server launches.

Codex discovers this hook set through `D:\Project\yasi\.codex\hooks.json`.

## Why It Exists

Foreground services such as `npm run dev`, `vite`, `python -m http.server`, and
`scripts\serve.py` can keep Codex's captured stdout or stderr handles open.
Codex waits for those handles to reach EOF, so the command can appear stuck
even when the server is already healthy.

Use the detached `ProcessStartInfo` pattern documented in `AGENT.md`:

- `UseShellExecute = $true`
- `CreateNoWindow = $true`
- `WindowStyle = Hidden`
- write the child PID to `tmp\*.pid`
- verify readiness from a separate short-lived command

## Trust Step

Project-local command hooks must be reviewed and trusted by Codex before they
run. Open `/hooks` in Codex after this change is present, review the
`PreToolUse` and `SessionStart` entries, then trust them.

## Scope

The guard intentionally blocks only high-confidence service startup patterns.
Long-running compute jobs, tests, builds, ASR benchmarks, and batch review
commands are allowed unless they match an unsafe service launch pattern.
