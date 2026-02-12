---
id: debug
name: Debug
description: |
  Systematic bug fixing with direct code execution.
  Cross-references error with design flow to find root cause.

  Triggers: debug, fix, bugfix, 디버그, 버그 수정
user-invocable: true
version: 2.0.0
triggers:
  - "debug"
  - "fix"
  - "bugfix"
  - "error fix"
requires: ["arch"]
platform: all
recommended_model: opus
allowed-tools:
  - Read
  - Write
  - StrReplace
  - Glob
  - Grep
  - LS
  - Shell
---

> ℹ️ **Global Rules Applied**:
> This skill adheres to the Archflow Global Rules defined in `rules/archflow-rules.md`.

# Debug Workflow

Systematically fix bugs by combining direct code execution with documentation analysis.

## 💡 Recommended Model

**Try Sonnet first** (Direct execution captures errors + documentation provides expected behavior)

→ For complex bugs (multi-file, flow analysis needed), **Opus** is recommended
→ If it doesn't work, retry with Opus

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read/Grep** | Request file path from user → ask for copy-paste |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB 3) OptionC" format |
| **Shell unavailable** | Request user to run commands and paste output |

## ⚠️ Debug Scope: E2E Issues

> **Debug skill is for E2E issues, not unit test failures.**
>
> - **Unit test failures** → Use `test` skill (test runs after build, required before commit)
> - **E2E issues** → Use `debug` skill (unit tests pass but functionality fails)

**Common E2E Issues:**
- BE↔FE communication mismatch (schema, request format)
- API contract violations
- Integration timing issues
- Environment-specific bugs

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              ├── spec.md      # spec skill output (input)
              ├── arch-be.md   # arch skill output - BE (input)
              ├── arch-fe.md   # arch skill output - FE (input)
              └── trace.md     # ← This skill's output
```

**serviceName inference**: Automatically extracted from input file path `docs/{serviceName}/spec.md` or `arch-be.md`

## 🔧 Execution Path Resolution

**Read from arch documents (Tech Stack section):**

| Field | Source | Example |
|-------|--------|---------|
| BE Path | `arch-be.md` → Tech Stack → BE Path | `apps/auth-api` |
| FE Path | `arch-fe.md` → Tech Stack → FE Path | `apps/auth-web` |
| Run Command (BE) | `arch-be.md` → Tech Stack → Run Command | `uv run uvicorn main:app` |
| Run Command (FE) | `arch-fe.md` → Tech Stack → Run Command | `npm run dev` |

> **Note**: These paths are set during `arch` skill execution and used by `build`, `test`, and `debug` skills.

---

## Phase 0: Skill Entry

### 0-0. Model and Environment Guidance (Display at start)

> 💡 **This skill should be run in Debug mode for best results.**
> Combines error location from Debug mode + expected behavior information from documentation.
>
> **Recommended Model**: Try Sonnet first, Opus for complex bugs
>
> **Required Documents** (`docs/{serviceName}/` folder):
> - spec.md (required)
> - arch.md (required)
> - trace.md (optional - will be created in this session if not present)

### 0-1. Collect Document Input

```json
{
  "title": "Start Bug Fix",
  "questions": [
    {
      "id": "has_requirements",
      "prompt": "Do you have a requirements document? (docs/{serviceName}/spec.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"},
        {"id": "no", "label": "No - I don't have it"}
      ]
    },
    {
      "id": "has_design",
      "prompt": "Do you have a design document? (docs/{serviceName}/arch.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"},
        {"id": "no", "label": "No - I don't have it"}
      ]
    },
    {
      "id": "has_changelog",
      "prompt": "Do you have a changelog? (docs/{serviceName}/trace.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"},
        {"id": "no", "label": "No - Will be created upon completion"}
      ]
    }
  ]
}
```

**Processing by response:**
- Requirements or design `no` → Show **General Debug Mode** guidance below
- Changelog `no` → Proceed with plan to create in Phase 3
- All `yes` → Request file paths → Proceed to Phase 1

### General Debug Mode (When documents unavailable)

When proceeding without requirements/design documents:

> ⚠️ **Proceeding in General Debug Mode.**
>
> Without documentation, we proceed with bug fixing using only error log and code analysis.
> - Cannot verify expected behavior from documentation
> - Cannot trace design flow
> - Changelog after fix will be saved to separate file
>
> Do you want to continue?

**General Debug Flow:**
1. Analyze error message/stack trace
2. Grep + Read related code
3. Estimate cause → Confirm with user
4. Implement fix
5. Specify separate location for changelog

### 0-2. Infer serviceName

Extract serviceName from provided file path:
- Input: `docs/alert/spec.md` or `docs/alert/arch.md`
- Extract: `serviceName = "alert"`
- Output path: `docs/alert/trace.md`

### 0-3. Verify Error Information

Verify information provided by Debug mode:
- Error message
- Stack trace (error location)
- Related variable state (if available)

Request additional information from user:
> "Please describe the error situation. If you see an error message or stack trace in Debug mode, please share it as well."

---

## Phase 1: Document Analysis

### 1-1. Load Documents

Read provided documents and identify key information:

| Document | Information to Extract |
|----------|----------------------|
| spec.md | Expected behavior, normal scenario |
| arch.md | Flow (call order), Code Mapping |
| trace.md | Recent changes (may be bug cause) |

### 1-2. Cross-reference Error Location with Design Flow

```
Error Location (stack trace):
  Example: alert_service.py:45 - NoneType error
        ↓
Check location in design document's Code Mapping:
  Example: AlertService.create_alert() → user_id handling
        ↓
Check expected behavior in requirements:
  Example: "Create notification for logged-in user"
        ↓
Identify mismatch
```

### 1-3. Report Analysis Results

```markdown
## Analysis Results

**Error Location**: {file}:{line} - {error message}

**Design Behavior**:
- {flow from design document for this part}

**Expected Behavior from Requirements**:
- {feature description from requirements}

**Recent Changes** (if changelog exists):
- {possibly related recent changes}

**Estimated Cause**:
- {cause hypothesis}

**Items Requiring Verification**:
- {if additional verification needed}
```

Confirm with user:
> "Is this analysis correct? If yes, I will proceed with the fix."

---

## Phase 2: Bug Fix

### 2-1. Confirm Cause

If analysis results are correct:
1. Read code at that location
2. Verify exact problem point
3. Decide fix direction

### 2-2. Implement Fix

Fix according to original design intent:
- Match requirements
- Match design flow
- Maintain existing code style

### 2-3. E2E Verification (Direct Execution)

> **Use Shell tool to run E2E environment and verify fix.**

**Step 1: Read Execution Config from arch documents**

```
BE Path: {from arch-be.md → Tech Stack → BE Path}
FE Path: {from arch-fe.md → Tech Stack → FE Path}
BE Run Command: {from arch-be.md → Tech Stack → Run Command}
FE Run Command: {from arch-fe.md → Tech Stack → Run Command}
```

**Step 2: Start E2E Environment (Shell)**

```bash
# 1. Start BE server (background)
cd {BE Path}
{BE Run Command} &

# 2. Wait for server ready (check port)
# Example: curl http://localhost:8000/health

# 3. Start FE or run E2E test
cd {FE Path}
{FE Run Command}  # or: npm run test:e2e
```

**Step 3: Verify Fix**

| Result | Action |
|--------|--------|
| ✅ Success (no errors) | Proceed to Phase 3 |
| ❌ Same error | Re-analyze → Return to 2-1 |
| ❌ New error | Analyze new error → Return to 2-1 |

> **Tight feedback loop**: See error → Fix → Re-run → Confirm fix immediately.

---

## Phase 3: Call trace Skill (Required)

> ⚠️ **Must call trace skill after analysis/fix completion.**

### 3-1. Call trace Skill

After analysis/fix completion, **must** call trace skill to record results.

**How to call:**
> "Calling trace skill to record this session's results."

Or guide user:
> "Analysis complete. Would you like to record this in the changelog?"

### 3-1.5. Prepare Code Mapping Changes for trace

When calling trace skill, extract Code Mapping changes from arch.md:

1. **Read arch.md** Code Mapping table (get current `#` numbers)
2. **Identify changes made during debug**:
   - Modified rows → record with original `#`, `Change = MODIFY`
   - New rows → assign `# = last_number + 1`, `Change = ADD`
   - Deleted rows → record with original `#`, `Change = DELETE`
3. **Pass to trace** in structured format:

```markdown
### Code Mapping Changes
| # | Feature | File | Class | Method | Action | Change | Synced |
|---|---------|------|-------|--------|--------|--------|--------|
| 3 | Auth | auth/svc.py | AuthSvc | validate() | Add null check | MODIFY | [ ] |
| 6 | Auth | auth/svc.py | AuthSvc | refresh() | Token refresh | ADD | [ ] |
```

> This structured format enables sync skill to directly apply changes to arch.md

### 3-2. Recording by Result Type

| Result Type | Content to Record in trace |
|-------------|-----------------------------------|
| **Code fix completed** | Symptom, cause, fix content, design impact |
| **External cause identified** | Symptom, external cause, recommended action |
| **Investigation ongoing/failed** | Symptom, investigation content, next steps |

### 3-3. If Not Called

User can manually call:
> "trace" or "write changelog"

When called in the same session, it will use the previous conversation's context (cause, fix content, etc.) as is.

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

### Verify trace Call

> ⚠️ **Have you recorded this in the changelog?**
>
> To record this session's results in the changelog:
> - Call "trace" skill
> - Or request "write changelog"
>
> **External causes and investigation failures are also worth recording.**

---

# Integration Flow

```
[spec] → docs/{serviceName}/spec.md
        ↓
[arch] → docs/{serviceName}/arch.md
        ↓
[build] → Implementation
        ↓
(Bug occurs)
        ↓
[debug] (Debug mode) → Analysis/fix
        ↓
[trace] → docs/{serviceName}/trace.md
        ↓ (when design impact exists)
[sync] → arch.md synchronization
```

---

# Important Notes

1. **Debug Mode Required**
   - Effectiveness decreases without runtime information from Debug mode
   - Error location and stack trace are essential

2. **Documentation Dependency**
   - Requirements/design documents must be accurate for effectiveness
   - If documentation and implementation mismatch, synchronization needed first

3. **Changelog Management**
   - All bug fixes should be recorded in changelog
   - Can reference for similar bugs in the future

4. **Complex Bugs**
   - For bugs spanning multiple files, Opus recommended
   - If not resolved at once, repeat: analysis → user confirmation → re-analysis
