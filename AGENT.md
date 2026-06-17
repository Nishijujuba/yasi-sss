# Project Agent Notes

## Python Environment

This project uses `uv` to manage the Python environment and dependencies.

Use the project virtual environment interpreter for Python commands:

```powershell
.venv\Scripts\python.exe
```

Common command forms:

```powershell
.venv\Scripts\python.exe -m pytest tests\python -q
.venv\Scripts\python.exe -m builder.render_pages
```

Avoid bare `python` for project work because the system Python may not have the
project dependencies installed, such as Pillow, NumPy, Pydantic, and pytest.

When dependency synchronization is needed and permissions allow it, prefer:

```powershell
uv sync --all-extras
```

## Task Resumption

When a task is interrupted because token usage is constrained and then resumed,
continue executing the original plan. Token availability has now recovered;
prioritize the quality and completion of the plan. Once a detailed plan has been
created, follow it strictly. Under no circumstances do you need to consider token
usage.

## Model Capacity Errors

When the error message `Selected model is at capacity. Please try a different
model.` appears, wait 10 seconds and resubmit the original request. Do not omit
steps, skip work, reduce quality, use shortcuts, lower the reasoning budget, or
make any other quality-reducing change because of this error.

## Long-Running Local Servers From Codex

Do not start a long-running server process from a Codex shell command if the
child process can inherit the shell command's stdout or stderr handles. Codex
waits for captured stdout/stderr to reach EOF; if a background server keeps
those handles open, the UI can show the shell command as still running even
after the server itself is healthy.

On Windows, `Start-Process` can also fail in this workspace when inherited
environment variables contain both `NO_PROXY` and `no_proxy`. That error is a
separate startup problem. The Codex hang is caused by inherited output handles
from the long-lived child process.

### PowerShell Coding Standard For Long-Running Services

When writing PowerShell that starts a server, watcher, browser companion,
Vite process, Python HTTP server, or any other long-lived local process from
Codex, follow these rules:

- Prefer a user-owned terminal for manual servers. Give the command to run
  there instead of making Codex own the service lifetime.
- If Codex must launch the service, start it as a detached process with
  `[System.Diagnostics.ProcessStartInfo]`.
- Set `UseShellExecute = $true` whenever the child process does not need a
  custom environment. This prevents the child from inheriting Codex's captured
  stdout and stderr pipes.
- Set `WindowStyle = Hidden` and `CreateNoWindow = $true` for helper services
  unless the user explicitly needs an interactive visible window.
- Write the child process id to `tmp\*.pid` so later turns can inspect or stop
  the exact helper process.
- Verify readiness with a separate short-lived command, such as
  `Invoke-WebRequest`, rather than waiting on the long-running process.
- Treat a foreground server command as blocking by design. Use it only for a
  deliberate diagnostic run with a small timeout.
- Do not use `Start-Job`, `Start-Process` with inherited output handles, or
  foreground `npm run dev` / `python -m http.server` from Codex for services
  expected to keep running.
- Do not set `RedirectStandardOutput = $true` or `RedirectStandardError =
  $true` unless the parent command remains alive and actively drains those
  streams.

Safe no-custom-environment template:

```powershell
$root = (Get-Location).Path
$pidPath = Join-Path $root 'tmp\serve-live.pid'

$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = Join-Path $root '.venv\Scripts\python.exe'
$psi.Arguments = 'scripts\serve.py --no-build'
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $true
$psi.CreateNoWindow = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

$process = [System.Diagnostics.Process]::Start($psi)
$process.Id | Set-Content -LiteralPath $pidPath -Encoding ASCII
```

If custom environment variables are required, launch a short PowerShell wrapper
as the detached process and keep all stdout/stderr away from Codex-owned pipes:

```powershell
$root = (Get-Location).Path
$scriptDir = 'C:\path\to\server'
$node = (Get-Command node.exe).Source
$sessionDir = Join-Path $root '.superpowers\brainstorm\session-id'
$pidPath = Join-Path $root 'tmp\brainstorm-server.pid'

$command = @"
`$env:BRAINSTORM_DIR = '$sessionDir'
`$env:BRAINSTORM_HOST = '127.0.0.1'
`$env:BRAINSTORM_URL_HOST = '127.0.0.1'
Set-Location '$scriptDir'
& '$node' 'server.cjs'
"@

$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = 'powershell.exe'
$psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -Command $([Management.Automation.Language.CodeGeneration]::QuoteArgument($command))"
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $true
$psi.CreateNoWindow = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

$process = [System.Diagnostics.Process]::Start($psi)
$process.Id | Set-Content -LiteralPath $pidPath -Encoding ASCII
```

When Codex must launch a local server itself, use one of these safer patterns:

```powershell
# Preferred for manual testing: run the server in a user-owned terminal.
cd D:\Project\yasi
npm run serve
```

```powershell
# If Codex must start it, use ShellExecute so the child does not inherit
# Codex's captured stdout/stderr pipes.
$root = (Get-Location).Path
$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = Join-Path $root '.venv\Scripts\python.exe'
$psi.Arguments = 'scripts\serve.py --no-build'
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $true
$psi.CreateNoWindow = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$p = [System.Diagnostics.Process]::Start($psi)
$p.Id | Set-Content 'tmp\serve-live.pid'
```

Avoid this flawed pattern for long-running servers:

```powershell
# Bad: UseShellExecute=false with inherited stdout/stderr can keep Codex waiting.
$psi.UseShellExecute = $false
[System.Diagnostics.Process]::Start($psi)
```

Also avoid `RedirectStandardOutput = $true` or `RedirectStandardError = $true`
unless the launching command will stay alive to consume those streams. Those
properties create parent-owned pipes. They do not write to the `$out` or `$err`
files by themselves.

After launching a server, verify it from a separate short-lived command instead
of waiting on the server process:

```powershell
Get-NetTCPConnection -LocalPort 4173 -State Listen
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4173/ |
  Select-Object StatusCode,RawContentLength
```
