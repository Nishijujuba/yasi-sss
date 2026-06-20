$ErrorActionPreference = "Stop"

$policy = @"
Yasi Codex server startup policy:
- Do not start long-running local servers as foreground Codex shell commands.
- Blocked examples include npm run dev, npm run serve, npm run preview, vite, python -m http.server, scripts/serve.py, uvicorn, streamlit, flask run, and similar long-lived service commands.
- The reason is stdout/stderr inheritance: Codex waits for captured output handles to close; a healthy foreground server can keep the shell tool running indefinitely.
- If Codex must launch a service, use AGENT.md's detached ProcessStartInfo pattern with UseShellExecute = true, WindowStyle Hidden, CreateNoWindow true, a tmp/*.pid file, and a separate short-lived readiness check.
- If a user-owned terminal is acceptable, ask the user to run the server there and use Codex only for short-lived verification commands.
"@

$output = @{
  hookSpecificOutput = @{
    hookEventName = "SessionStart"
    additionalContext = $policy
  }
}

$output | ConvertTo-Json -Depth 8 -Compress
