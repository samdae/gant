# Archflow Global Rules
These rules apply globally to all Archflow skills. Individual skills must adhere unless explicitly overridden.

## 1. Skill Workflow

### 1-1. Workflow Sequences
| Type | Sequence |
|------|----------|
| **Feature (BE)** | `spec` → `arch-be` → `check-be` → `pre-build-be` → `build-be` → `test-be` |
| **Feature (FE)** | `spec` → `arch-be` → `check-be` → `ui` → `arch-fe` → `check-fe` → `pre-build-fe` → `build-fe` → `test-fe` |
| **Bugfix** | `debug` → `trace` → `sync` |
| **Enhance** | `reinforce` → `arch` → `check` → `pre-build` → `build` → `test` |
| **Legacy** | `reverse` → `reinforce` (optional) → `check` |

> **FE workflow requires BE arch first** — Frontend design depends on backend API definitions.

### 1-2. Enforcement Rules
| Rule | Description |
|------|-------------|
| **Arch → Check** | After `arch-be.md` or `arch-fe.md` created/modified, `check` **MUST** run |
| **Check → Pre-build** | After `check` passes, `pre-build` **MUST** run to verify environment/secrets |
| **Build → Test** | After `build` completes, `test` **MUST** run. Commit only after all tests pass |
| **Debug → Trace → Sync** | After `debug` completes, `trace` and `sync` **MUST** run. Commit only after all complete |
| **Docs → Commit** | Changes to `/docs/` files should be committed. Skip if git not initialized |

### 1-3. Next Step Guidance
At the end of each skill, guide user to next skill in workflow.
Example: After `check-be` passes → "Next: Run `/pre-build` to verify environment readiness."

## 2. Communication
This skill is written in English for universal compatibility. **Always respond in user's language** unless explicitly requested otherwise. If uncertain, ask.

## 3. Document Version Control
After document changes, git commit is recommended. Format: `docs({serviceName}): {skillName} - {change summary}`. If git unavailable or not a repo → skip and continue.

## 4. Identifier Management
**Code Mapping `#` Rule**: Always use `max(existing #) + 1` for new rows. NEVER reuse deleted numbers (history traceability).
**Requirement ID `FR-{number}` Rule**: Always use `max(existing number) + 1`. NEVER reuse deleted numbers.

## 5. Logical Inconsistency Handling
When user feedback conflicts with existing design/requirements/purpose:
1. **Detect**: Identify specific contradiction
2. **Report**: Present "Existing Content" vs "User Feedback"
3. **Resolve** via AskQuestion with options:
   - **Keep original**: Ignore new feedback and maintain the current state
   - **Accept new**: Revise the original content to match the new feedback
   - **Merge**: Incorporate elements of both (requires explanation of how)
   - **Re-debate / Clarify**: Request further discussion or specific details
