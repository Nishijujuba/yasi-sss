# Yasi ASR Timing Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for implementation and `superpowers:test-driven-development` inside each implementation subagent. Use `superpowers:verification-before-completion` before any completion claim. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `.agents/skills/yasi-asr-timing-reconciliation/`, run the Section 01 Whisper model benchmark, choose the first skill default, and produce the scripts needed to generate ASR timing evidence, reconciliation reports, review artifacts, and final `yasi.transcript-timings.v1` timing assets.

**Architecture:** The new skill uses local Whisper word timestamps as timing evidence, reconciles ASR words against official `transcript.json`, and keeps generated benchmark artifacts under `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\`. Release artifacts keep the existing frontend timing contract and promote the final review trace under `build/review/transcript-timing/`.

**Tech Stack:** Python 3 in `D:\Project\yasi\.venv\Scripts\python.exe`, local Whisper CLI at `D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe`, pytest, existing pack data under `public/packs/cambridge-10/test-1/listening`, existing release validator in `builder/validate_pack.py`.

---

## Coordination Model

**Coordinator:** Main Codex session. Owns task ordering, subagent prompts, integration, conflict checks, and final user report.

**Parallel implementation subagents:**

- **Subagent A: Artifact Contracts** owns fixtures, artifact schemas, and serialization tests.
- **Subagent B: Whisper Benchmark** owns Whisper invocation, `asr-timing-evidence.json`, and model benchmark runner.
- **Subagent C: Reconciliation Core** owns token normalization, sequence alignment, anchor extraction, interpolation, and review item generation.
- **Subagent D: Finalize And Validator** owns final `transcript-timings.json`, release audit promotion, and `builder/validate_pack.py` integration.
- **Subagent E: Skill Packaging Docs** owns `SKILL.md`, usage examples, and skill validation.
- **Subagent V: Independent Acceptance** runs after A-E integration. It receives no implementation task and performs acceptance review only.

**Parallelization rule:** Subagents A, B, and C can start in parallel after Task 0 because their file ownership is separate. Subagent D starts after A and C produce contracts and validator expectations. Subagent E starts after the CLI names and artifacts stabilize. Subagent V starts only after all implementation subagents report done and the coordinator has integrated changes.

**File ownership:**

- A owns `.agents/skills/yasi-asr-timing-reconciliation/fixtures/*` and `tests/python/test_asr_timing_artifacts.py`.
- B owns `.agents/skills/yasi-asr-timing-reconciliation/scripts/whisper_evidence.py`, `.agents/skills/yasi-asr-timing-reconciliation/scripts/benchmark_whisper.py`, and `tests/python/test_whisper_evidence.py`.
- C owns `.agents/skills/yasi-asr-timing-reconciliation/scripts/reconcile_tokens.py` and `tests/python/test_asr_reconcile_tokens.py`.
- D owns `.agents/skills/yasi-asr-timing-reconciliation/scripts/asr_timing_reconcile.py`, `.agents/skills/yasi-asr-timing-reconciliation/scripts/validate_timings.py`, `builder/validate_pack.py`, and `tests/python/test_validate_pack.py`.
- E owns `.agents/skills/yasi-asr-timing-reconciliation/SKILL.md` and related plan/doc touchups.

## Task 0: Coordinator Preflight

**Files:**

- Read: `docs/adr/0008-use-asr-timing-reconciliation-for-transcript-shadowing.md`
- Read: `docs/superpowers/specs/2026-06-17-transcript-shadowing-design.md`
- Read: `docs/superpowers/plans/2026-06-18-asr-timing-reconciliation-skill.md`

- [ ] **Step 1: Record dirty worktree**

Run:

```powershell
git status --short
```

Expected: dirty worktree may exist. Coordinator must avoid reverting unrelated changes.

- [ ] **Step 2: Verify local paths**

Run:

```powershell
Test-Path -LiteralPath 'D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe'
Test-Path -LiteralPath 'D:\Project\yasi\public\packs\cambridge-10\test-1\listening\assets\audio\section-01.mp3'
Test-Path -LiteralPath 'D:\Project\yasi\public\packs\cambridge-10\test-1\listening\transcript.json'
```

Expected: three `True` values.

- [ ] **Step 3: Create coordination checklist**

Track these execution lanes:

```text
A Artifact Contracts
B Whisper Benchmark
C Reconciliation Core
D Finalize And Validator
E Skill Packaging Docs
V Independent Acceptance
```

## Task 1A: Artifact Contracts Subagent

**Subagent:** A Artifact Contracts.

**Files:**

- Create: `.agents/skills/yasi-asr-timing-reconciliation/fixtures/sample-asr-timing-evidence.json`
- Create: `.agents/skills/yasi-asr-timing-reconciliation/fixtures/sample-reconciliation-report.json`
- Create: `.agents/skills/yasi-asr-timing-reconciliation/fixtures/sample-alignment-review.json`
- Create: `tests/python/test_asr_timing_artifacts.py`

- [ ] **Step 1: Write failing artifact tests**

Test required fields:

```python
def test_asr_timing_evidence_contract():
    payload = load_fixture("sample-asr-timing-evidence.json")
    assert payload["schemaVersion"] == "yasi.asr-timing-evidence.v1"
    assert payload["engine"] == "whisper"
    assert payload["model"] in {"small", "medium", "large-v3"}
    assert payload["sourceAudio"].endswith("section-01.mp3")
    assert payload["words"][0].keys() >= {"index", "word", "normalized", "start", "end"}

def test_reconciliation_report_contract():
    payload = load_fixture("sample-reconciliation-report.json")
    assert payload["schemaVersion"] == "yasi.reconciliation-report.v1"
    assert payload["gateOutcome"] in {"ready-for-finalize", "needs-review", "rerun-asr"}
    assert payload["matchTypeCounts"].keys() >= {"exact", "fuzzy", "interpolated", "split", "merged", "unmatched"}
    assert payload["metrics"]["anchorCoverage"] >= 0

def test_alignment_review_contract():
    payload = load_fixture("sample-alignment-review.json")
    item = payload["mappingReviews"][0]
    assert item["matchType"] in {"exact", "fuzzy", "interpolated", "split", "merged", "unmatched"}
    assert item["decision"] in {"pending", "approved", "corrected", "rejected"}
    assert item["officialToken"].keys() >= {"section", "segmentOrder", "tokenIndex", "text"}
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_asr_timing_artifacts.py -q
```

Expected: fail because fixtures and helpers are absent.

- [ ] **Step 3: Create fixture payloads**

Create minimal valid fixture payloads using Section 01 examples and repo-root-relative `reviewArtifact`.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_asr_timing_artifacts.py -q
```

Expected: pass.

## Task 1B: Whisper Benchmark Subagent

**Subagent:** B Whisper Benchmark.

**Files:**

- Create: `.agents/skills/yasi-asr-timing-reconciliation/scripts/whisper_evidence.py`
- Create: `.agents/skills/yasi-asr-timing-reconciliation/scripts/benchmark_whisper.py`
- Create: `tests/python/test_whisper_evidence.py`

- [ ] **Step 1: Write failing tests for Whisper command construction**

Expected command shape:

```powershell
$env:PYTHONUTF8='1'
D:\Project\video2pdf\kimi\.venv\Scripts\whisper.exe D:\Project\yasi\public\packs\cambridge-10\test-1\listening\assets\audio\section-01.mp3 --model small --model_dir "$env:USERPROFILE\.cache\whisper" --language en --word_timestamps True --output_format json --output_dir D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\section-01\small
```

Test that the Python wrapper sets `PYTHONUTF8=1`, accepts `small|medium|large-v3`, and rejects any model name outside the benchmark set.

- [ ] **Step 2: Implement `whisper_evidence.py`**

Responsibilities:

- invoke Whisper without Qwen imports;
- normalize Whisper JSON segments into `asr-timing-evidence.json`;
- include command, model, source audio, generated time, and word `start`/`end`;
- write under the model-specific Section 01 run directory, for example `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\section-01\small\`.

- [ ] **Step 3: Implement `benchmark_whisper.py`**

CLI contract:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\benchmark_whisper.py --section 1 --models small medium large-v3 --overwrite
```

Expected outputs per model:

```text
asr-timing-evidence.json
whisper.stdout.log
whisper.stderr.log
```

- [ ] **Step 4: Run unit tests**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_whisper_evidence.py -q
```

Expected: pass without running real Whisper; subprocess is monkeypatched.

## Task 1C: Reconciliation Core Subagent

**Subagent:** C Reconciliation Core.

**Files:**

- Create: `.agents/skills/yasi-asr-timing-reconciliation/scripts/reconcile_tokens.py`
- Create: `tests/python/test_asr_reconcile_tokens.py`

- [ ] **Step 1: Write failing tests for token normalization**

Cover apostrophes, hyphens, punctuation, casing, currency, numbers, and IELTS answer-near risk flags.

- [ ] **Step 2: Write failing tests for sequence alignment**

Use synthetic data:

```text
Official: good morning world tours my name is jamie
ASR:      good morning world tours my name is jamie
```

Expected: all `exact`, anchor coverage `1.0`.

Use mismatch data:

```text
Official: good morning world tours my name is jamie
ASR:      good morning world tours my name is jammy
```

Expected: final token becomes `fuzzy` or review-required depending similarity threshold.

- [ ] **Step 3: Write failing interpolation tests**

Expected automatic interpolation only when:

```text
gapTokens <= 3
anchorSpanSeconds <= 2.5
risk == false
```

Expected `pending` review when any condition fails.

- [ ] **Step 4: Implement `reconcile_tokens.py`**

Responsibilities:

- flatten official transcript tokens into `{section, segmentOrder, tokenIndex, text, normalized, answerRefs}`;
- flatten ASR words from `asr-timing-evidence.json`;
- dynamic-programming alignment;
- derive `matchType`;
- compute `anchorCoverage`, `unmatchedRate`, `pendingReviewRate`, `longestUnanchoredGap`;
- produce draft word timings plus review items.

- [ ] **Step 5: Run core tests**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_asr_reconcile_tokens.py -q
```

Expected: pass.

## Task 2: Coordinator Integration Checkpoint

**Files:**

- Read all files from Tasks 1A, 1B, 1C.

- [ ] **Step 1: Check ownership conflicts**

Run:

```powershell
git status --short .agents/skills/yasi-asr-timing-reconciliation tests/python
```

Expected: no two subagents changed the same implementation file.

- [ ] **Step 2: Run combined unit tests**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_asr_timing_artifacts.py tests/python/test_whisper_evidence.py tests/python/test_asr_reconcile_tokens.py -q
```

Expected: pass before D starts.

## Task 3D: Finalize And Validator Subagent

**Subagent:** D Finalize And Validator.

**Files:**

- Create: `.agents/skills/yasi-asr-timing-reconciliation/scripts/asr_timing_reconcile.py`
- Create: `.agents/skills/yasi-asr-timing-reconciliation/scripts/validate_timings.py`
- Modify: `builder/validate_pack.py`
- Modify: `tests/python/test_validate_pack.py`
- Create: `tests/python/test_asr_timing_reconcile_cli.py`

- [ ] **Step 1: Write failing CLI tests**

CLI contracts:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\asr_timing_reconcile.py --section 1 --model small --evidence-input D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\section-01\small\asr-timing-evidence.json --draft

D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\asr_timing_reconcile.py --finalize-review --review-input D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\section-01\small\alignment-review.json --output D:\Project\yasi\public\packs\cambridge-10\test-1\listening\transcript-timings.json
```

Expected artifacts:

```text
reconciliation-report.json
alignment-review.json
transcript-timings.draft.json
transcript-timings.json
```

- [ ] **Step 2: Implement CLI orchestration**

Responsibilities:

- load official `transcript.json`;
- load `asr-timing-evidence.json`;
- call `reconcile_tokens.py`;
- write `reconciliation-report.json`;
- write draft timings and `alignment-review.json`;
- finalize only when review decisions are approved or corrected;
- set `reviewArtifact` as repo-root-relative path under `build/review/transcript-timing/cambridge-10-test-1-listening/alignment-review.json`.

- [ ] **Step 3: Port or wrap timing validation**

Move reusable validation rules from `.agents/skills/yasi-forced-alignment/scripts/validate_timings.py` into the new skill path. Keep the old skill historical.

- [ ] **Step 4: Update release validation tests**

Add cases in `tests/python/test_validate_pack.py`:

- release fails when `reviewArtifact` is missing;
- release fails when `reviewArtifact` is pack-relative for release audit;
- release fails when review artifact has `pending`;
- release fails when review coverage is missing for a required review timing;
- release passes when `reviewArtifact` is `build/review/transcript-timing/cambridge-10-test-1-listening/alignment-review.json`.

- [ ] **Step 5: Run validator tests**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_asr_timing_reconcile_cli.py tests/python/test_validate_pack.py -q
```

Expected: pass.

## Task 4E: Skill Packaging Docs Subagent

**Subagent:** E Skill Packaging Docs.

**Files:**

- Create: `.agents/skills/yasi-asr-timing-reconciliation/SKILL.md`
- Modify: `docs/superpowers/plans/2026-06-18-asr-timing-reconciliation-skill.md` only when benchmark changes default model decision.

- [ ] **Step 1: Create `SKILL.md`**

Required sections:

- purpose and superseding relationship to `yasi-forced-alignment`;
- local paths;
- no-Qwen primary workflow;
- benchmark command;
- artifact contracts;
- reconciliation algorithm;
- release audit promotion;
- failure handling;
- validation commands.

- [ ] **Step 2: Add command examples**

Examples must include:

```powershell
$env:PYTHONUTF8='1'
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\benchmark_whisper.py --section 1 --models small medium large-v3 --overwrite

D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\asr_timing_reconcile.py --section 1 --model small --draft
```

The second command uses `small` as the Section 01 smoke example. After Task 5 chooses the benchmark winner, `SKILL.md` must replace the default model reference with the selected model.

- [ ] **Step 3: Validate skill metadata**

Run:

```powershell
$env:PYTHONUTF8='1'
D:\Project\yasi\.venv\Scripts\python.exe C:\Users\juju\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\Project\yasi\.agents\skills\yasi-asr-timing-reconciliation
```

Expected: validation succeeds.

## Task 5: Section 01 Benchmark Execution

**Owner:** Coordinator dispatches Subagent B or a fresh Benchmark Runner subagent after Tasks 1B, 1C, and 3D are integrated.

**Files/outputs:**

- Generate under `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\section-01\small\`
- Generate under `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\section-01\medium\`
- Generate under `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\section-01\large-v3\`

- [ ] **Step 1: Run benchmark**

Run:

```powershell
$env:PYTHONUTF8='1'
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\benchmark_whisper.py --section 1 --models small medium large-v3 --overwrite
```

Expected: each model directory contains:

```text
asr-timing-evidence.json
reconciliation-report.json
alignment-review.json
transcript-timings.draft.json
whisper.stdout.log
whisper.stderr.log
```

- [ ] **Step 2: Compare models**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe .agents\skills\yasi-asr-timing-reconciliation\scripts\benchmark_whisper.py --section 1 --models small medium large-v3 --compare-only
```

Expected: output table includes `anchorCoverage`, `unmatchedRate`, `pendingReviewRate`, `longestUnanchoredGap`, runtime, and default recommendation.

- [ ] **Step 3: Select default model**

Apply gate:

```text
run completes
anchorCoverage >= 0.95
unmatchedRate <= 0.02
pendingReviewRate <= 0.10
longestUnanchoredGap <= 8 official tokens
```

Expected: choose the smallest passing model. If none pass, leave default unset and report `rerun-asr`.

- [ ] **Step 4: Update docs with benchmark conclusion**

Modify:

- `.agents/skills/yasi-asr-timing-reconciliation/SKILL.md`
- `docs/superpowers/plans/2026-06-18-asr-timing-reconciliation-skill.md`

Record chosen model and evidence summary. Do not copy temporary benchmark artifacts into `public/packs`.

## Task 6: Independent Acceptance Subagent

**Subagent:** V Independent Acceptance. This subagent must be fresh and must not have implemented any previous task.

**Scope:** Read-only review plus allowed verification commands. It may write a short acceptance report under `D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\acceptance-report.md`.

- [ ] **Step 1: Review requirements against implementation**

Read:

- `docs/adr/0008-use-asr-timing-reconciliation-for-transcript-shadowing.md`
- `docs/superpowers/specs/2026-06-17-transcript-shadowing-design.md`
- `docs/superpowers/plans/2026-06-18-yasi-asr-timing-reconciliation-execution.md`
- `.agents/skills/yasi-asr-timing-reconciliation/SKILL.md`

Check every requirement has code, tests, and validation evidence.

- [ ] **Step 2: Run full Python verification**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python -q
```

Expected: pass.

- [ ] **Step 3: Run skill validation**

Run:

```powershell
$env:PYTHONUTF8='1'
D:\Project\yasi\.venv\Scripts\python.exe C:\Users\juju\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\Project\yasi\.agents\skills\yasi-asr-timing-reconciliation
```

Expected: pass.

- [ ] **Step 4: Verify no Qwen model path in new primary workflow**

Run:

```powershell
rg -n "Qwen|qwen|ForcedAligner|D:\\model-repo" .agents/skills/yasi-asr-timing-reconciliation
```

Expected: no matches in executable primary workflow. Historical warnings in docs are acceptable only when explicitly marked as superseded context.

- [ ] **Step 5: Verify benchmark artifacts**

Run:

```powershell
Get-ChildItem -Recurse -LiteralPath 'D:\Project\yasi\待删除\yasi-asr-timing-reconciliation\section-01' | Select-Object FullName,Length
```

Expected: each benchmark model has evidence, report, review, draft timings, and logs.

- [ ] **Step 6: Write acceptance report**

Report format:

```text
ACCEPTANCE STATUS: PASS | FAIL
Verified commands:
- ...
Benchmark default model:
- ...
Blocking issues:
- ...
Residual risks:
- ...
```

## Final Coordinator Verification

- [ ] **Step 1: Read Subagent V acceptance report**

If status is `FAIL`, coordinator dispatches targeted fix subagent and repeats acceptance.

- [ ] **Step 2: Run final focused commands**

Run:

```powershell
D:\Project\yasi\.venv\Scripts\python.exe -m pytest tests/python/test_asr_timing_artifacts.py tests/python/test_whisper_evidence.py tests/python/test_asr_reconcile_tokens.py tests/python/test_asr_timing_reconcile_cli.py tests/python/test_validate_pack.py -q
$env:PYTHONUTF8='1'
D:\Project\yasi\.venv\Scripts\python.exe C:\Users\juju\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\Project\yasi\.agents\skills\yasi-asr-timing-reconciliation
```

Expected: both commands pass.

- [ ] **Step 3: Summarize benchmark result**

Report:

- selected default model;
- metrics for `small`, `medium`, `large-v3`;
- any pending review burden;
- exact paths of generated temporary artifacts;
- exact release audit path rule.
