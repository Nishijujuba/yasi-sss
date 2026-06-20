$ErrorActionPreference = "Stop"

function Get-StringProperty {
  param(
    [Parameter(Mandatory = $true)] $Object,
    [Parameter(Mandatory = $true)] [string] $Name
  )

  if ($null -eq $Object) {
    return $null
  }

  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property -or $null -eq $property.Value) {
    return $null
  }

  return [string] $property.Value
}

function Test-Regex {
  param(
    [Parameter(Mandatory = $true)] [string] $Text,
    [Parameter(Mandatory = $true)] [string] $Pattern
  )

  return [System.Text.RegularExpressions.Regex]::IsMatch(
    $Text,
    $Pattern,
    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
  )
}

function New-AllowResult {
  exit 0
}

function New-DenyResult {
  param(
    [Parameter(Mandatory = $true)] [string] $Reason,
    [Parameter(Mandatory = $true)] [string] $Command
  )

  $policy = @"
Yasi Codex server startup policy:
- Do not start long-running local servers as foreground Codex shell commands.
- Blocked examples include npm run dev, npm run serve, npm run preview, vite, python -m http.server, scripts/serve.py, uvicorn, streamlit, flask run, and similar long-lived service commands.
- The reason is stdout/stderr inheritance: Codex waits for captured output handles to close; a healthy foreground server can keep the shell tool running indefinitely.
- If Codex must launch a service, use AGENT.md's detached ProcessStartInfo pattern with UseShellExecute = true, WindowStyle Hidden, CreateNoWindow true, a tmp/*.pid file, and a separate short-lived readiness check.
- If a user-owned terminal is acceptable, ask the user to run the server there and use Codex only for short-lived verification commands.
"@

  $decisionReason = @"
Blocked by yasi server startup guard.

Category: $Reason

$policy

Rejected command:
$Command
"@

  $output = @{
    systemMessage = "Blocked a foreground or unsafe long-running server launch. Use the detached startup pattern from AGENT.md."
    hookSpecificOutput = @{
      hookEventName = "PreToolUse"
      permissionDecision = "deny"
      permissionDecisionReason = $decisionReason
      additionalContext = $policy
    }
  }

  $output | ConvertTo-Json -Depth 12 -Compress
  exit 0
}

$stdinText = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($stdinText)) {
  New-AllowResult
}

try {
  $event = $stdinText | ConvertFrom-Json -ErrorAction Stop
} catch {
  New-AllowResult
}

$toolInput = $event.PSObject.Properties["tool_input"].Value
$command = Get-StringProperty -Object $toolInput -Name "command"
if ([string]::IsNullOrWhiteSpace($command)) {
  New-AllowResult
}

$normalized = [System.Text.RegularExpressions.Regex]::Replace($command, "\s+", " ").Trim()

$safeDetachedMarkers = @(
  'useshellexecute\s*=\s*\$true',
  '\[system\.diagnostics\.process\]::start\s*\(',
  '\bstart-process\b',
  '\bcmd(\.exe)?\s*/c\s+start\b'
)

$hasSafeDetachedMarker = $false
foreach ($pattern in $safeDetachedMarkers) {
  if (Test-Regex -Text $normalized -Pattern $pattern) {
    $hasSafeDetachedMarker = $true
    break
  }
}

$foregroundServerPatterns = @(
  '(^|[;&|]\s*)npm(\.cmd|\.ps1)?\s+run\s+(dev|serve|preview)\b',
  '(^|[;&|]\s*)(pnpm|yarn|bun)\s+(dev|serve|preview)\b',
  '(^|[;&|]\s*)(npx\s+)?vite(\.cmd|\.ps1)?(\s|$)',
  '(^|[;&|]\s*)(python(\.exe)?|py(\.exe)?|\.venv[\\/]+scripts[\\/]+python(\.exe)?)\s+-m\s+http\.server\b',
  '(^|[;&|]\s*)(python(\.exe)?|py(\.exe)?|\.venv[\\/]+scripts[\\/]+python(\.exe)?)\s+scripts[\\/]+serve\.py\b',
  '(^|[;&|]\s*)(uvicorn|streamlit)\b',
  '(^|[;&|]\s*)flask\s+run\b',
  '(^|[;&|]\s*)(python(\.exe)?|py(\.exe)?)\s+-m\s+(uvicorn|streamlit|flask)\b',
  '(^|[;&|]\s*)next\s+dev\b',
  '(^|[;&|]\s*)(node(\.exe)?\s+)?server\.cjs\b'
)

$matchesForegroundServer = $false
foreach ($pattern in $foregroundServerPatterns) {
  if (Test-Regex -Text $normalized -Pattern $pattern) {
    $matchesForegroundServer = $true
    break
  }
}

$serverIntentPatterns = @(
  'npm(\.cmd|\.ps1)?\s+run\s+(dev|serve|preview)\b',
  '\b(pnpm|yarn|bun)\s+(dev|serve|preview)\b',
  '\b(npx\s+)?vite(\.cmd|\.ps1)?\b',
  '\bhttp\.server\b',
  'scripts[\\/]+serve\.py\b',
  '\b(uvicorn|streamlit)\b',
  '\bflask\s+run\b',
  '\bnext\s+dev\b',
  '\bserver\.cjs\b'
)

$hasServerIntent = $false
foreach ($pattern in $serverIntentPatterns) {
  if (Test-Regex -Text $normalized -Pattern $pattern) {
    $hasServerIntent = $true
    break
  }
}

$unsafeProcessMarkers = @(
  'useshellexecute\s*=\s*\$false',
  'redirectstandard(output|error)\s*=\s*\$true',
  '\bstart-job\b'
)

$hasUnsafeProcessMarker = $false
foreach ($pattern in $unsafeProcessMarkers) {
  if (Test-Regex -Text $normalized -Pattern $pattern) {
    $hasUnsafeProcessMarker = $true
    break
  }
}

if ($hasServerIntent -and $hasUnsafeProcessMarker) {
  New-DenyResult -Reason "unsafe-detached-process-pattern" -Command $command
}

if ($matchesForegroundServer -and -not $hasSafeDetachedMarker) {
  New-DenyResult -Reason "foreground-long-running-server-command" -Command $command
}

New-AllowResult
