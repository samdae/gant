---
id: test
name: Test
description: |
  Generate and/or run tests with scoped targeting.
  Default scope is change-based (git diff vs arch commit).
  Supports BE (API/unit) and FE (Playwright headless E2E).

  Triggers: test, tests, run tests, qa, verify, 테스트, 검증
user-invocable: true
version: 1.0.0
triggers:
  - "test"
  - "tests"
  - "run tests"
  - "qa"
  - "verify"
requires: []
platform: all
recommended_model: sonnet
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - LS
  - Shell
  - AskQuestion
---

> ℹ️ **Global Rules Applied**:
> This skill adheres to the Archflow Global Rules defined in `rules/archflow-rules.md`.

# Test Workflow

Generate and/or execute tests for backend and frontend changes with minimal scope.
Default scope is change-based (git diff), aligned to the arch commit baseline.

## 💡 Recommended Model

**Sonnet** recommended (code generation task) / Opus for complex test logic

→ Test generation is pattern-based; high-performance model unnecessary for most cases

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read/Grep** | Request file path from user → ask for copy-paste |
| **Shell** | Ask user to run commands manually, provide exact commands |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB 3) OptionC" format |

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              ├── spec.md        # FR references for scope
              ├── arch-be.md     # Code Mapping for BE tests
              ├── arch-fe.md     # Code Mapping for FE tests
              └── test-report.md # ← This skill's output (optional)
```

**Test file locations** (project conventions):
- BE: `tests/`, `__tests__/`, `*_test.py`, `*.test.ts`, etc.
- FE: `e2e/`, `tests/e2e/`, `*.spec.ts`, etc.

---

## Phase 0: Skill Entry

### 0-0. Model Guidance (Display at start)

> 💡 **This skill recommends the Sonnet model.**
> Test generation is pattern-based and doesn't require high reasoning.
> Use Opus only for complex test logic or edge case generation.

### 0-0.5. Prerequisite (Flexible)

| Scenario | Prerequisite | Notes |
|----------|--------------|-------|
| **Standard flow** | Run `/build` first | Test implementation code |
| **Document-based** | `arch.md` only | Generate tests from design before implementation |
| **Legacy code** | Existing code | Add tests to existing codebase, no `/build` needed |

> ⚠️ **Framework Auto-Install (Important)**
> - If mode is `run` and test framework is not detected, **will ask to install**
> - FE: Offers to install Playwright automatically
> - BE: Detects pytest/jest/vitest/go and guides installation

### 0-1. Context-Aware Entry (Smart Shortcut)

**Check recent conversation history for `build` execution.**

**If `build` context found (e.g., built BE):**
```json
{
  "title": "Smart Test Context",
  "questions": [
    {
      "id": "smart_test",
      "prompt": "Detected recent BE build. Run tests with recommended settings?\n(Target: BE, Mode: Both, Scope: Change-based)",
      "options": [
        {"id": "yes", "label": "Yes - Run immediately"},
        {"id": "no", "label": "No - Configure manually"}
      ]
    }
  ]
}
```
**Process:**
- `yes` → Skip to **Phase 1** (Environment Check & Execution)
- `no` / Context not found → Proceed to **0-2. Manual Configuration**

### 0-2. Manual Configuration (Collect Target and Mode)

**Use AskQuestion to collect inputs:**

```json
{
  "title": "Test Configuration",
  "questions": [
    {
      "id": "target",
      "prompt": "What do you want to test?",
      "options": [
        {"id": "be", "label": "Backend - API/unit tests"},
        {"id": "fe", "label": "Frontend - Playwright E2E tests"},
        {"id": "both", "label": "Both - BE + FE tests"}
      ]
    },
    {
      "id": "mode",
      "prompt": "What do you want to do?",
      "options": [
        {"id": "generate", "label": "Generate - Write test files only"},
        {"id": "run", "label": "Run - Execute existing tests only"},
        {"id": "both", "label": "Both - Generate then run"}
      ]
    }
  ]
}
```

**Processing by response:**
- Load appropriate profile based on target selection
- `be` → **Read `profiles/be.md`** from this skill folder
- `fe` → **Read `profiles/fe.md`** from this skill folder
- `both` → Read both profiles

### 0-2. Collect Scope

```json
{
  "title": "Test Scope",
  "questions": [
    {
      "id": "scope_type",
      "prompt": "How do you want to scope the tests?",
      "options": [
        {"id": "change", "label": "Change-based (default) - Test files changed since arch commit"},
        {"id": "fr", "label": "FR-based - Test specific requirement IDs (FR-001, FR-002...)"},
        {"id": "module", "label": "Module-based - Test specific modules from Code Mapping"},
        {"id": "custom", "label": "Custom paths - Specify files/directories manually"},
        {"id": "all", "label": "All - Run all tests (may be slow)"}
      ]
    }
  ]
}
```

### 0-3. Infer serviceName

If design documents provided, extract serviceName:
- Input: `docs/alert/arch-be.md`
- Extract: `serviceName = "alert"`

If no documents provided, ask user or use project root.

---

## Phase 1: Resolve Test Scope

### 1-1. Change-based Scope (Default)

**Find arch commit baseline:**

```bash
# Find latest arch commit for this service
git log --oneline --grep="docs({serviceName}): arch" -1
# Example output: a1b2c3d docs(alert): arch - initial design
```

**Get changed files since arch commit:**

```bash
git diff --name-only <arch_commit>..HEAD
```

**Map changed files to test targets:**

| Changed File Pattern | Test Target |
|---------------------|-------------|
| `src/services/*.py` | `tests/services/test_*.py` |
| `src/api/*.py` | `tests/api/test_*.py` |
| `src/components/*.tsx` | `e2e/*.spec.ts` |
| `src/pages/*.tsx` | `e2e/*.spec.ts` |

### 1-2. FR-based Scope

**Ask for FR IDs:**

```json
{
  "title": "Select Requirements",
  "questions": [
    {
      "id": "fr_ids",
      "prompt": "Which requirements do you want to test? (comma-separated)\nExample: FR-001, FR-002",
      "options": [
        {"id": "input", "label": "I'll type the FR IDs"},
        {"id": "show_list", "label": "Show me the list from spec.md"}
      ]
    }
  ]
}
```

**Map FR → Code Mapping → Files:**

1. Read `docs/{serviceName}/spec.md` for FR list
2. Read `docs/{serviceName}/arch-*.md` for Code Mapping
3. Find rows where FR matches
4. Extract file paths as test targets

### 1-3. Module-based Scope

**Extract modules from Code Mapping:**

```json
{
  "title": "Select Modules",
  "questions": [
    {
      "id": "modules",
      "prompt": "Which modules do you want to test?",
      "options": [
        {"id": "auth", "label": "Authentication module"},
        {"id": "alert", "label": "Alert module"},
        {"id": "user", "label": "User module"}
      ],
      "allow_multiple": true
    }
  ]
}
```

Options are dynamically generated from Code Mapping sections.

### 1-4. Custom Paths Scope

> "Please provide the file or directory paths you want to test."
> "Example: `src/services/alert_service.py`, `tests/api/`"

### 1-5. All Scope

Use project's full test suite path:
- BE: `tests/` or configured test directory
- FE: `e2e/` or configured E2E directory

---

## Phase 2: Detect Test Environment

### 2-1. BE Test Environment

**Auto-detect from project files:**

| File | Framework | Run Command |
|------|-----------|-------------|
| `pytest.ini`, `pyproject.toml` (pytest) | pytest | `pytest {paths}` |
| `package.json` (jest) | jest | `npm test -- {paths}` |
| `package.json` (vitest) | vitest | `npx vitest {paths}` |
| `go.mod` | go test | `go test {paths}` |

**If detection fails, ask user:**

```json
{
  "title": "BE Test Framework",
  "questions": [
    {
      "id": "be_framework",
      "prompt": "What test framework does this project use for backend?",
      "options": [
        {"id": "pytest", "label": "pytest (Python)"},
        {"id": "jest", "label": "Jest (Node.js)"},
        {"id": "vitest", "label": "Vitest (Node.js)"},
        {"id": "go", "label": "go test (Go)"},
        {"id": "junit", "label": "JUnit (Java)"},
        {"id": "other", "label": "Other (I'll provide command)"}
      ]
    }
  ]
}
```

### 2-2. FE Test Environment

**Check for Playwright:**

```bash
# Check package.json for playwright
grep -l "playwright" package.json
```

**If not installed:**

```json
{
  "title": "Playwright Not Found",
  "questions": [
    {
      "id": "install_playwright",
      "prompt": "Playwright is not installed. Do you want to add it?",
      "options": [
        {"id": "yes", "label": "Yes - Add Playwright to dependencies"},
        {"id": "no", "label": "No - Skip FE tests"},
        {"id": "other", "label": "Use different E2E framework"}
      ]
    }
  ]
}
```

**If yes, add Playwright:**

```bash
npm install -D @playwright/test
npx playwright install
```

---

## Phase 3: Generate Tests (if mode includes generate)

### 3-1. Load Profile

Read the appropriate profile from `profiles/be.md` or `profiles/fe.md`.

Profile contains:
- Test file naming convention
- Test structure template
- Framework-specific patterns
- Assertion patterns

### 3-2. Analyze Target Code

For each target file:

1. **Read the implementation file**
2. **Read the design document section** (if available)
3. **Identify testable units:**

| Target Type | Testable Units |
|-------------|----------------|
| Service class | Public methods |
| API endpoint | Request/Response combinations |
| Component | User interactions, states |
| Utility function | Input/output combinations |

### 3-3. Generate Test Cases

**For each testable unit, generate:**

```yaml
test_cases:
  - name: "test_{method}_success"
    type: "happy path"
    description: "Normal operation succeeds"
    
  - name: "test_{method}_invalid_input"
    type: "error case"
    description: "Invalid input returns error"
    
  - name: "test_{method}_edge_case"
    type: "edge case"
    description: "Boundary conditions handled"
```

### 3-4. Write Test Files

Use templates from loaded profile (`profiles/be.md` or `profiles/fe.md`).

> 📎 **See profiles for full templates:**
> - BE: `profiles/be.md` - pytest/jest/vitest/go templates
> - FE: `profiles/fe.md` - Playwright E2E templates

### 3-5. Report Generated Files

```markdown
## Tests Generated

| # | File | Test Count | Coverage Target |
|---|------|------------|-----------------|
| 1 | `tests/services/test_alert_service.py` | 5 | `src/services/alert_service.py` |
| 2 | `tests/api/test_alert_api.py` | 8 | `src/api/alert.py` |
| 3 | `e2e/alert.spec.ts` | 4 | Alert pages |

**Total**: 17 tests generated
```

---

## Phase 4: Run Tests (if mode includes run)

### 4-1. Execute Tests

**Run with scope filter:**

```bash
# BE (pytest example)
pytest tests/services/test_alert_service.py tests/api/test_alert_api.py -v

# FE (Playwright)
npx playwright test e2e/alert.spec.ts --headed=false
```

### 4-2. Capture Results

Parse test output for:
- Total tests
- Passed
- Failed
- Skipped
- Duration

### 4-3. Handle Failures

**If tests fail:**

```json
{
  "title": "Test Failures Detected",
  "questions": [
    {
      "id": "failure_action",
      "prompt": "{N} tests failed. How do you want to proceed?",
      "options": [
        {"id": "show", "label": "Show failure details"},
        {"id": "fix", "label": "Attempt to fix failing tests"},
        {"id": "skip", "label": "Continue without fixing"},
        {"id": "debug", "label": "Switch to /debug skill"}
      ]
    }
  ]
}
```

**If "fix" selected:**
- Analyze failure message
- Identify if issue is in test or implementation
- If test issue: fix test
- If implementation issue: recommend `/debug`

---

## Phase 5: Generate Report

### 5-1. Test Report Template

```markdown
# Test Report: {serviceName}

> Generated: {date}
> Scope: {scope_type}
> Target: {BE/FE/Both}

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | {total} |
| Passed | {passed} ✅ |
| Failed | {failed} ❌ |
| Skipped | {skipped} ⏭️ |
| Duration | {duration}s |
| Coverage | {coverage}% (if available) |

## Scope Details

### Files Tested
| # | File | Tests | Result |
|---|------|-------|--------|
| 1 | {file} | {count} | ✅/❌ |

### FR Coverage
| Req ID | Tests | Status |
|--------|-------|--------|
| FR-001 | 5 | ✅ All passed |
| FR-002 | 3 | ❌ 1 failed |

## Failures (if any)

### {test_name}
- **File**: {file_path}
- **Error**: {error_message}
- **Suggestion**: {fix_suggestion}

## Generated Tests (if mode includes generate)

| File | Tests Added |
|------|-------------|
| {file} | {count} |

## Next Steps

- **All passed**: Implementation verified ✅
- **Failures exist**: Run `/debug` to investigate
- **Need more tests**: Run `/test` with different scope
```

### 5-2. Save Report (Optional)

```json
{
  "title": "Save Report",
  "questions": [
    {
      "id": "save_report",
      "prompt": "Do you want to save the test report?",
      "options": [
        {"id": "yes", "label": "Yes - Save to docs/{serviceName}/test-report.md"},
        {"id": "no", "label": "No - Display only"}
      ]
    }
  ]
}
```

---

## Quality Gate

### Pre-run Validation

| Check | Criteria | On Fail |
|-------|----------|---------|
| Implementation exists | Target files exist | Guide to `/build` |
| Test framework installed | Framework detected | Offer to install |
| Scope not empty | At least 1 test target | Ask for different scope |

### Post-run Validation

| Check | Criteria | On Fail |
|-------|----------|---------|
| No crashes | All tests completed | Report error |
| Pass rate | Configurable threshold | Warn user |

---

## Completion Report

```markdown
## Test Execution Complete

### Summary
| Item | Value |
|------|-------|
| Service | {serviceName} |
| Scope | {scope_type}: {scope_details} |
| Mode | {generate/run/both} |
| Target | {BE/FE/Both} |

### Results
| Metric | BE | FE | Total |
|--------|----|----|-------|
| Tests | {n} | {n} | {total} |
| Passed | {n} | {n} | {total} |
| Failed | {n} | {n} | {total} |

### Files
- **Generated**: {list of generated test files}
- **Executed**: {list of executed test files}

### Next Steps
> - **All passed** → Implementation verified
> - **Failures** → Run `/debug` to investigate
> - **Need coverage** → Run `/test` with `all` scope
```

---

# Integration Flow

```
[spec] → docs/{serviceName}/spec.md (FR references)
        ↓
[arch] → docs/{serviceName}/arch-*.md (Code Mapping)
        ↓
[build] → Implementation
        ↓
[test] → Generate and/or run tests
        │
        ├── ✅ All passed → Done
        │
        └── ❌ Failures → [debug] → [trace] → [sync]
```

---

# Important Notes

1. **Change-based is the default**
   - Minimizes test scope for faster feedback
   - Uses arch commit as baseline (implementation is always after arch)

2. **Git is optional but recommended**
   - If git unavailable, ask user for file list
   - Fallback: module-based or custom scope

3. **Test frameworks are auto-detected**
   - Reads package.json, pyproject.toml, go.mod, etc.
   - Falls back to asking user

4. **Playwright for FE is default**
   - Headless by default for CI compatibility
   - Can offer to install if not present

5. **Tests are scoped to implementation**
   - Only tests files that exist and have been implemented
   - Skips files marked as `[ ]` in Code Mapping Impl column

6. **FR traceability**
   - Tests can reference FR IDs in docstrings/comments
   - Enables requirement coverage reporting
