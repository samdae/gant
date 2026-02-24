---
id: test
name: test
description: |
  Generate and/or run tests with scoped targeting.
  Default scope: change-based (git diff vs arch commit).
  Supports BE (API/unit) and FE (Playwright E2E).
  Triggers: test, run tests, qa, verify
user-invocable: true
version: 1.0.0
triggers: ["test", "tests", "run tests", "qa", "verify"]
requires: []
platform: all
recommended_model: sonnet
allowed-tools: [Read, Write, Glob, Grep, LS, Shell, AskQuestion]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.

# Test Workflow

Generate and/or execute tests with minimal scope. Default: change-based (git diff).
**Model**: Sonnet recommended. Opus for complex test logic only.

## Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read/Grep** | Request file path from user -> ask for copy-paste |
| **Shell** | Ask user to run commands manually, provide exact commands |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB" format |

## Document Structure

```
docs/{serviceName}/
  spec.md        # FR references for scope
  arch-be.md     # Code Mapping for BE tests
  arch-fe.md     # Code Mapping for FE tests
  test-report.md # output (optional)
```

Test file locations: BE: `tests/`, `__tests__/`, `*_test.py`, `*.test.ts` / FE: `e2e/`, `tests/e2e/`, `*.spec.ts`

---

## Phase 0: Skill Entry

### 0-0.5. Prerequisite (Flexible)

| Scenario | Prerequisite | Notes |
|----------|--------------|-------|
| **Standard flow** | Run `/build` first | Test implementation code |
| **Document-based** | `arch.md` only | Generate tests from design before implementation |
| **Legacy code** | Existing code | Add tests to existing codebase, no `/build` needed |

> WARNING: **Framework Auto-Install** - If mode is `run` and test framework is not detected, will ask to install. FE: Offers Playwright. BE: Detects pytest/jest/vitest/go and guides installation.

### 0-1. Context-Aware Entry (Smart Shortcut)

Check recent conversation for `build` execution:

```json
{"title":"Smart Test Context","questions":[{"id":"smart_test","prompt":"Detected recent BE build. Run tests with recommended settings?\n(Target: BE, Mode: Both, Scope: Change-based)","options":[{"id":"yes","label":"Yes - Run immediately"},{"id":"no","label":"No - Configure manually"}]}]}
```

- `yes` -> Skip to Phase 1
- `no` / context not found -> Proceed to 0-2

### 0-2. Manual Configuration

```json
{"title":"Test Configuration","questions":[
  {"id":"target","prompt":"What do you want to test?","options":[
    {"id":"be","label":"Backend - API/unit tests"},
    {"id":"fe","label":"Frontend - Playwright E2E tests"},
    {"id":"both","label":"Both - BE + FE tests"}
  ]},
  {"id":"mode","prompt":"What do you want to do?","options":[
    {"id":"generate","label":"Generate - Write test files only"},
    {"id":"run","label":"Run - Execute existing tests only"},
    {"id":"both","label":"Both - Generate then run"}
  ]}
]}
```

Load profile: `profiles/be.md` and/or `profiles/fe.md` based on target.

### 0-2b. Collect Scope

```json
{"title":"Test Scope","questions":[{"id":"scope_type","prompt":"How do you want to scope the tests?","options":[
  {"id":"change","label":"Change-based (default) - Test files changed since arch commit"},
  {"id":"fr","label":"FR-based - Test specific requirement IDs (FR-001, FR-002...)"},
  {"id":"module","label":"Module-based - Test specific modules from Code Mapping"},
  {"id":"custom","label":"Custom paths - Specify files/directories manually"},
  {"id":"all","label":"All - Run all tests (may be slow)"}
]}]}
```

### 0-3. Infer serviceName

From design doc path (e.g., `docs/alert/arch-be.md` -> `serviceName = "alert"`) or ask user.

---

## Phase 1: Resolve Test Scope

### 1-1. Change-based Scope (Default)

Find arch commit baseline:

```bash
git log --oneline --grep="docs({serviceName}): arch" -1
# Example: a1b2c3d docs(alert): arch - initial design
```

Get changed files since arch commit:

```bash
git diff --name-only <arch_commit>..HEAD
```

Map changed files to test targets:

| Changed File Pattern | Test Target |
|---------------------|-------------|
| `src/services/*.py` | `tests/services/test_*.py` |
| `src/api/*.py` | `tests/api/test_*.py` |
| `src/components/*.tsx` | `e2e/*.spec.ts` |
| `src/pages/*.tsx` | `e2e/*.spec.ts` |

### 1-2. FR-based Scope

```json
{"title":"Select Requirements","questions":[{"id":"fr_ids","prompt":"Which requirements do you want to test? (comma-separated)\nExample: FR-001, FR-002","options":[{"id":"input","label":"I'll type the FR IDs"},{"id":"show_list","label":"Show me the list from spec.md"}]}]}
```

Map FR -> Code Mapping -> Files: Read spec.md for FR list -> Read arch-*.md for Code Mapping -> Find matching rows -> Extract file paths.

### 1-3. Module-based Scope

```json
{"title":"Select Modules","questions":[{"id":"modules","prompt":"Which modules do you want to test?","options":[{"id":"dynamic","label":"(dynamically generated from Code Mapping sections)"}],"allow_multiple":true}]}
```

Options are dynamically generated from Code Mapping sections.

### 1-4. Custom Paths Scope

User provides file/directory paths.

### 1-5. All Scope

Use project's full test suite path: BE: `tests/` / FE: `e2e/`

---

## Phase 2: Detect Test Environment

### 2-1. BE Test Environment

Auto-detect from project files:

| File | Framework | Run Command |
|------|-----------|-------------|
| `pytest.ini`, `pyproject.toml` (pytest) | pytest | `pytest {paths}` |
| `package.json` (jest) | jest | `npm test -- {paths}` |
| `package.json` (vitest) | vitest | `npx vitest {paths}` |
| `go.mod` | go test | `go test {paths}` |

If detection fails, ask user (pytest/jest/vitest/go test/JUnit/other).

### 2-2. FE Test Environment

Check for Playwright in package.json. If not installed:

```json
{"title":"Playwright Not Found","questions":[{"id":"install_playwright","prompt":"Playwright is not installed. Do you want to add it?","options":[
  {"id":"yes","label":"Yes - Add Playwright to dependencies"},
  {"id":"no","label":"No - Skip FE tests"},
  {"id":"other","label":"Use different E2E framework"}
]}]}
```

If yes: `npm install -D @playwright/test && npx playwright install`

---

## Phase 3: Generate Tests (if mode includes generate)

### 3-1. Load Profile

Read `profiles/be.md` or `profiles/fe.md` for: test file naming, structure template, framework patterns, assertion patterns.

### 3-2. Analyze Target Code

For each target file: read implementation, read design doc section, identify testable units:

| Target Type | Testable Units |
|-------------|----------------|
| Service class | Public methods |
| API endpoint | Request/Response combinations |
| Component | User interactions, states |
| Utility function | Input/output combinations |

### 3-3. Generate Test Cases

For each testable unit:

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

### 3-5. Report Generated Files

```markdown
## Tests Generated

| # | File | Test Count | Coverage Target |
|---|------|------------|-----------------|
| 1 | `tests/services/test_alert_service.py` | 5 | `src/services/alert_service.py` |
| 2 | `tests/api/test_alert_api.py` | 8 | `src/api/alert.py` |

**Total**: {N} tests generated
```

---

## Phase 4: Run Tests (if mode includes run)

### 4-1. Execute Tests

```bash
# BE (pytest example)
pytest tests/services/test_alert_service.py tests/api/test_alert_api.py -v

# FE (Playwright)
npx playwright test e2e/alert.spec.ts --headed=false
```

### 4-2. Capture Results

Parse output: total, passed, failed, skipped, duration.

### 4-3. Handle Failures

```json
{"title":"Test Failures Detected","questions":[{"id":"failure_action","prompt":"{N} tests failed. How do you want to proceed?","options":[
  {"id":"show","label":"Show failure details"},
  {"id":"fix","label":"Attempt to fix failing tests"},
  {"id":"skip","label":"Continue without fixing"},
  {"id":"debug","label":"Switch to /debug skill"}
]}]}
```

If "fix": analyze if test or implementation issue. Test issue -> fix test. Implementation issue -> recommend `/debug`.

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
| Passed | {passed} |
| Failed | {failed} |
| Skipped | {skipped} |
| Duration | {duration}s |
| Coverage | {coverage}% (if available) |

## Scope Details

### Files Tested
| # | File | Tests | Result |
|---|------|-------|--------|
| 1 | {file} | {count} | pass/fail |

### FR Coverage
| Req ID | Tests | Status |
|--------|-------|--------|
| FR-001 | 5 | All passed |
| FR-002 | 3 | 1 failed |

## Failures (if any)

### {test_name}
- **File**: {file_path}
- **Error**: {error_message}
- **Suggestion**: {fix_suggestion}

## Next Steps

- **All passed**: Implementation verified
- **Failures exist**: Run `/debug` to investigate
- **Need more tests**: Run `/test` with different scope
```

### 5-2. Save Report (Optional)

Ask to save to `docs/{serviceName}/test-report.md` or display only.

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

### Next Steps
> - All passed -> Implementation verified
> - Failures -> Run `/debug` to investigate
> - Need coverage -> Run `/test` with `all` scope
```

---

# Integration Flow

```
[spec] -> docs/{serviceName}/spec.md (FR references)
        |
[arch] -> docs/{serviceName}/arch-*.md (Code Mapping)
        |
[build] -> Implementation
        |
[test] -> Generate and/or run tests
        |
        +-- All passed -> Done
        |
        +-- Failures -> [debug] -> [trace] -> [sync]
```

---

# Important Notes

1. **Change-based is default** - Minimizes test scope for faster feedback. Uses arch commit as baseline.
2. **Git is optional but recommended** - If unavailable, fallback to module-based or custom scope.
3. **Test frameworks are auto-detected** - Reads package.json, pyproject.toml, go.mod, etc. Falls back to asking user.
4. **Playwright for FE is default** - Headless by default for CI compatibility. Can offer to install if not present.
5. **Tests are scoped to implementation** - Only tests files that exist. Skips files marked as `[ ]` in Code Mapping Impl column.
6. **FR traceability** - Tests can reference FR IDs in docstrings/comments. Enables requirement coverage reporting.
