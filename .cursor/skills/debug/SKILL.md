---
id: debug
name: debug
description: |
  Systematic bug fixing with direct code execution.
  Cross-references error with design flow to find root cause.
  Triggers: debug, fix, bugfix
user-invocable: true
version: 2.0.0
triggers: ["debug", "fix", "bugfix", "error fix"]
requires: ["arch"]
platform: all
recommended_model: opus
allowed-tools: [Read, Write, StrReplace, Glob, Grep, LS, Shell]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.
> **Code Mapping `#` Rule**: Always use `max(existing #) + 1` for new rows. NEVER reuse deleted numbers.

**Model**: Try Sonnet first. For complex bugs (multi-file, flow analysis), use Opus.

# Debug Workflow

Systematically fix bugs by combining direct code execution with documentation analysis.

## Scope

Debug is for **E2E issues**, not unit test failures.
- Unit test failures -> use `/test`
- E2E issues (unit tests pass but functionality fails) -> use `/debug`

Common E2E issues: BE-FE mismatch, API contract violations, integration timing, environment-specific bugs.

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read/Grep | Request file path from user -> ask for copy-paste |
| AskQuestion | "Please select: 1) OptionA 2) OptionB 3) OptionC" format |
| Shell | Ask user to run commands and paste output |

## Document Structure

```
docs/{serviceName}/
  ├── spec.md      # Input (expected behavior)
  ├── arch-be.md   # Input (flow, Code Mapping)
  ├── arch-fe.md   # Input (flow, Code Mapping)
  └── trace.md     # Output (this skill produces)
```

## Execution Path Resolution

Read from arch documents (Tech Stack section):

| Field | Source | Example |
|-------|--------|---------|
| BE Path | arch-be.md -> Tech Stack -> BE Path | `apps/auth-api` |
| FE Path | arch-fe.md -> Tech Stack -> FE Path | `apps/auth-web` |
| Run Command (BE) | arch-be.md -> Tech Stack -> Run Command | `uv run uvicorn main:app` |
| Run Command (FE) | arch-fe.md -> Tech Stack -> Run Command | `npm run dev` |

---

## Phase 0: Skill Entry

### 0-0. Model and Environment Guidance

> **Required Documents** (`docs/{serviceName}/`):
> - spec.md (required), arch.md (required), trace.md (optional - created if absent)

### 0-1. Collect Document Input

```json
{"title":"Start Bug Fix","questions":[{"id":"has_requirements","prompt":"Do you have a requirements document? (docs/{serviceName}/spec.md)","options":[{"id":"yes","label":"Yes - I will provide via @filepath"},{"id":"no","label":"No - I don't have it"}]},{"id":"has_design","prompt":"Do you have a design document? (docs/{serviceName}/arch.md)","options":[{"id":"yes","label":"Yes - I will provide via @filepath"},{"id":"no","label":"No - I don't have it"}]},{"id":"has_changelog","prompt":"Do you have a changelog? (docs/{serviceName}/trace.md)","options":[{"id":"yes","label":"Yes - I will provide via @filepath"},{"id":"no","label":"No - Will be created upon completion"}]}]}
```

**Processing:**
- Requirements or design `no` -> General Debug (below)
- Changelog `no` -> Will create in Phase 3
- All `yes` -> Request file paths -> Phase 1

### General Debug (When documents unavailable)

> **WARNING**: Proceeding without documentation. Bug fixing uses only error log and code analysis.
> Cannot verify expected behavior or trace design flow.

General Debug Flow:
1. Analyze error message/stack trace
2. Grep + Read related code
3. Estimate cause -> Confirm with user
4. Implement fix
5. Specify separate location for changelog

### 0-2. Infer serviceName

From file path: `docs/alert/spec.md` -> serviceName = "alert" -> Output: `docs/alert/trace.md`

### 0-3. Verify Error Information

Collect: error message, stack trace, variable state (if available).
> "Please describe the error situation. If you have an error message or stack trace, please share it."

---

## Phase 1: Document Analysis

### 1-1. Load Documents

| Document | Extract |
|----------|---------|
| spec.md | Expected behavior, normal scenario |
| arch.md | Flow (call order), Code Mapping |
| trace.md | Recent changes (possible cause) |

### 1-2. Cross-reference Error Location with Design Flow

```
Error Location (stack trace)
  -> Check Code Mapping (which method)
  -> Check requirements (expected behavior)
  -> Identify mismatch
```

### 1-3. Report Analysis Results

```markdown
## Analysis Results

**Error Location**: {file}:{line} - {error message}
**Design Behavior**: {flow from design document}
**Expected Behavior**: {feature description from requirements}
**Recent Changes**: {possibly related recent changes}
**Estimated Cause**: {cause hypothesis}
**Items Requiring Verification**: {additional checks needed}
```

Confirm with user: "Is this analysis correct? If yes, I will proceed with the fix."

---

## Phase 2: Bug Fix

### 2-1. Confirm Cause

Read code at error location, verify exact problem point, decide fix direction.

### 2-2. Implement Fix

Fix matching: requirements, design flow, existing code style.

### 2-3. E2E Verification (Direct Execution)

**Step 1**: Read execution config from arch documents (BE/FE Path, Run Commands).

**Step 2**: Start E2E environment (Shell):
```bash
cd {BE Path} && {BE Run Command} &
# Wait for server ready (health check)
cd {FE Path} && {FE Run Command}  # or: npm run test:e2e
```

**Step 3**: Verify fix:

| Result | Action |
|--------|--------|
| Success (no errors) | Proceed to Phase 3 |
| Same error | Re-analyze -> Return to 2-1 |
| New error | Analyze new error -> Return to 2-1 |

> Tight feedback loop: See error -> Fix -> Re-run -> Confirm fix immediately.

---

## Phase 3: Call trace Skill (Required)

**WARNING**: Must call trace skill after analysis/fix completion.

### 3-1. Call trace Skill

After fix: "Calling trace skill to record this session's results."
Or guide: "Analysis complete. Would you like to record this in the changelog?"

### 3-1.5. Prepare Code Mapping Changes for trace

1. Read arch.md Code Mapping table (get current `#` numbers)
2. Identify changes: modified rows (MODIFY), new rows (ADD, # = last+1), deleted rows (DELETE)
3. Pass to trace in structured format:

```markdown
### Code Mapping Changes
| # | Feature | File | Class | Method | Action | Change | Synced |
|---|---------|------|-------|--------|--------|--------|--------|
| 3 | Auth | auth/svc.py | AuthSvc | validate() | Add null check | MODIFY | [ ] |
| 6 | Auth | auth/svc.py | AuthSvc | refresh() | Token refresh | ADD | [ ] |
```

> This structured format enables sync skill to directly apply changes to arch.md

### 3-2. Recording by Result Type

| Result Type | Content to Record |
|-------------|-------------------|
| Code fix completed | Symptom, cause, fix content, design impact |
| External cause identified | Symptom, external cause, recommended action |
| Investigation ongoing/failed | Symptom, investigation content, next steps |

### 3-3. If Not Called

User can manually call: "trace" or "write changelog". Same session context will be used.

---

## Phase 4: Completion Report

```markdown
## Bug Fix Complete

### Analysis/Fix Summary
| Item | Content |
|------|---------|
| Symptom | {original bug symptom} |
| Cause | {identified cause} |
| Result Type | Code fix / External cause / Under investigation |
| Modified Files | {file list or "none"} |

### Test Method (if fixed)
1. {Verify with reproduction scenario}
2. {How to verify normal behavior}

### Recurrence Prevention (Required Checklist)
- [ ] Add tests (if applicable)
- [ ] Add guard/validation logic (if applicable)
- [ ] Add logging/monitoring (if applicable)

**Recurrence Probability**: High / Medium / Low
```

**WARNING**: Have you recorded this in the changelog? Call "trace" or "write changelog".
External causes and investigation failures are also worth recording.

---

## Integration Flow

```
[spec] -> spec.md -> [arch] -> arch.md -> [build] -> Implementation
  -> (Bug occurs) -> [debug] -> Analysis/fix
    -> [trace] -> trace.md -> (design impact) -> [sync] -> arch.md
```

## Important Notes

1. **Runtime Info Helps** - Providing error messages and stack traces improves effectiveness
2. **Documentation Dependency** - Docs must be accurate; if doc-impl mismatch, sync first
3. **Changelog Management** - All bug fixes should be recorded in trace
4. **Complex Bugs** - Multi-file bugs -> use Opus; if unresolved, repeat analysis -> confirmation -> re-analysis
