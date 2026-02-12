---
id: ui
name: UI
description: |
  Generate UI specification from requirements and backend API design.
  Derives screen list, component hierarchy, and user interactions from endpoints.

  Triggers: ui, ui spec, 화면 설계, UI 명세
user-invocable: true
version: 1.0.0
triggers:
  - "ui"
  - "ui spec"
  - "screen design"
requires: ["spec", "arch-be"]
platform: all
recommended_model: opus
allowed-tools:
  - Read
  - Write
  - Glob
  - LS
  - AskQuestion
---

> ℹ️ **Global Rules Applied**:
> This skill adheres to the Archflow Global Rules defined in `rules/archflow-rules.md`.

# UI Workflow

Generate UI specification by analyzing requirements and backend API endpoints.
Derives screen list, component hierarchy, states, and user interactions.

## 💡 Recommended Model

**Opus Required** - UI derivation requires domain knowledge and pattern matching

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read** | Request user to copy-paste document content |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB" format |

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              ├── spec.md        # Input (requirements)
              ├── arch-be.md     # Input (backend API)
              └── ui.md          # ← This skill's output
```

---

## Phase -1: Service Discovery

1. **Scan `docs/`** for service directories.
2. **Select Service** (Auto or User selection).
3. **Resolve Paths**:
   - `spec.md` = `docs/{serviceName}/spec.md`
   - `arch-be.md` = `docs/{serviceName}/arch-be.md`

## Phase 0: Skill Entry

### 0-0. Model Guidance

> 💡 **This skill recommends the Opus model.**
> UI derivation requires understanding domain patterns and component relationships.
>
> **Required Documents** (`docs/{serviceName}/` folder):
> - spec.md (required) - requirements specification
> - arch-be.md (required) - backend API design with endpoints

### 0-1. Collect Document Input

**If Service Discovery successful:**
- Verify `spec.md` and `arch-be.md` exist.
- If both exist, **auto-load and skip this step**.
- If missing, guide user to run required skills (`/spec` or `/arch`).

**If Service Discovery failed:**
```json
{
  "title": "UI Specification",
  "questions": [
    {
      "id": "has_spec",
      "prompt": "Do you have a requirements document? (docs/{serviceName}/spec.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"},
        {"id": "no", "label": "No - Run /spec first"}
      ]
    },
    {
      "id": "has_arch_be",
      "prompt": "Do you have a backend design document? (docs/{serviceName}/arch-be.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"},
        {"id": "no", "label": "No - Run /arch (Backend) first"}
      ]
    }
  ]
}
```

**Processing by response:**
- Either `no` → Guide to run required skill first
- Both `yes` → Request file paths → Proceed to 0-1.5

### 0-1.5. Responsive Option

```json
{
  "title": "Target Platform",
  "questions": [
    {
      "id": "responsive",
      "prompt": "What platforms are you targeting?",
      "options": [
        {"id": "mobile", "label": "Mobile only - Mobile viewport wireframes"},
        {"id": "desktop", "label": "Desktop only - Desktop viewport wireframes"},
        {"id": "responsive", "label": "Both (Responsive) - Mobile First approach"}
      ]
    }
  ]
}
```

**Processing by response:**
- `mobile` → Generate wireframes for mobile viewport (375px width)
- `desktop` → Generate wireframes for desktop viewport (1280px+ width)
- `responsive` → Generate Mobile First wireframes with breakpoint hints

**Breakpoint hints for responsive:**
```yaml
breakpoints:
  mobile: "< 640px"     # Default view
  tablet: "640-1024px"  # Adjust layout
  desktop: "> 1024px"   # Full layout
```

→ Record selection in ui.md header, apply to all wireframes

### 0-2. Infer serviceName

Extract serviceName from provided file path:
- Input: `docs/blog/spec.md` or `docs/blog/arch-be.md`
- Extract: `serviceName = "blog"`
- Output path: `docs/blog/ui.md`

### 0-3. Load Documents

Read and analyze:
1. **spec.md** - Extract functional requirements
2. **arch-be.md** - Extract API endpoints, request/response schemas

---

## Phase 1: Derive Screen List

### 1-1. Analyze Endpoints

For each endpoint in arch-be.md API Specification:

| Endpoint Pattern | Screen Derivation |
|------------------|-------------------|
| `GET /resources` | List screen |
| `GET /resources/:id` | Detail screen |
| `POST /resources` | Create screen/form |
| `PUT /resources/:id` | Edit screen/form |
| `DELETE /resources/:id` | Delete confirmation (modal) |
| `POST /auth/login` | Login screen |
| `POST /auth/register` | Registration screen |

### 1-2. Map Requirements to Screens

Cross-reference spec.md requirements with derived screens:
- Which requirement maps to which screen?
- Are there screens without clear requirements? (flag for confirmation)
- Are there requirements without screens? (may need additional endpoints)

### 1-3. Generate Screen List

```markdown
## 1. Screen List

| # | Screen | Route | Related Endpoints | Auth Required | Spec Reference |
|---|--------|-------|-------------------|---------------|----------------|
| 1 | {name} | {route} | {endpoints} | Yes/No | {spec section} |
```

### 1-4. User Checkpoint

> "I've derived {N} screens from the API endpoints. Please review:
> 
> {Screen List Table}
> 
> Should I proceed with detailed UI specifications?"

---

## Phase 2: Screen Specifications

For each screen, generate detailed UI specification:

### 2-1. UI Components (ASCII Wireframe)

```
┌─────────────────────────────────────────────┐
│ [Logo]                    [Login/Profile]   │
├─────────────────────────────────────────────┤
│                                             │
│  Main content area                          │
│                                             │
└─────────────────────────────────────────────┘
```

### 2-2. Component Hierarchy

```yaml
{ScreenName}Page:
  - Header:
      - Logo
      - Navigation
      - AuthButton
  - MainContent:
      - {Feature}Section:
          - {Component}
          - {Component}
  - Footer
```

### 2-3. States Definition

| State | Trigger | UI Behavior |
|-------|---------|-------------|
| loading | Initial fetch | Show skeleton/spinner |
| empty | No data | Show empty state message |
| error | API error | Show error message + retry |
| loaded | Data received | Render content |

### 2-4. User Interactions

| # | Action | Trigger | API Call | Result |
|---|--------|---------|----------|--------|
| 1 | {action} | {event} | {endpoint} | {outcome} |

---

## Phase 3: Shared Components

### 3-1. Identify Reusable Components

Analyze all screens and extract common patterns:

| Component | Used In | Props | Description |
|-----------|---------|-------|-------------|
| Header | All pages | - | Global navigation |
| AuthButton | Header | isLoggedIn, user | Login/profile toggle |
| Pagination | List pages | page, total, onChange | Page navigation |
| ConfirmModal | Delete actions | title, onConfirm | Confirmation dialog |
| LoadingSkeleton | All pages | variant | Loading placeholder |
| EmptyState | List pages | message, action | No data state |
| ErrorMessage | Forms | message | Validation/API error |

### 3-2. Design System Reference

```yaml
recommendation:
  ui_library: "{recommended library}"      # e.g., shadcn/ui, Radix UI
  styling: "{styling approach}"            # e.g., Tailwind CSS
  icons: "{icon library}"                  # e.g., Lucide Icons
  
patterns:
  layout: "{layout pattern}"               # e.g., max-w-4xl mx-auto
  spacing: "{spacing system}"              # e.g., Tailwind default scale
  typography: "{typography approach}"      # e.g., prose class for content
```

---

## Phase 4: Generate ui.md

### 4-1. Output Template

```markdown
# UI Specification: {Feature Name}

> Created: {date}
> Service: {serviceName}
> Platform: {mobile|desktop|responsive}
> Requirements: docs/{serviceName}/spec.md
> Backend API: docs/{serviceName}/arch-be.md

## 0. Responsive Strategy

```yaml
platform: "{mobile|desktop|responsive}"
breakpoints:                              # Only for responsive
  mobile: "< 640px"
  tablet: "640-1024px"
  desktop: "> 1024px"
approach: "Mobile First"                  # Default for responsive
```

---

## 1. Screen List

| # | Screen | Route | Related Endpoints | Auth Required |
|---|--------|-------|-------------------|---------------|
| 1 | {ScreenName} | {/route} | {GET /api/...} | Yes/No |

---

## 2. Screen Specifications

### 2.1 {ScreenName} ({/route})

**Purpose**: {brief description}

**UI Components**:
```
{ASCII wireframe}
```

**Component Hierarchy**:
```yaml
{component tree}
```

**States**:
| State | UI Behavior |
|-------|-------------|
| loading | {behavior} |
| empty | {behavior} |
| error | {behavior} |
| loaded | {behavior} |

**User Interactions**:
| # | Action | Trigger | API Call | Result |
|---|--------|---------|----------|--------|
| 1 | {action} | {event} | {endpoint} | {outcome} |

---

(Repeat for each screen...)

---

## 3. Shared Components

| Component | Props | Usage |
|-----------|-------|-------|
| {name} | {props} | {where used} |

---

## 4. Design System Reference

```yaml
recommendation:
  ui_library: "{library}"
  styling: "{approach}"
  icons: "{library}"
```

---

## 5. Next Steps

> Run `/arch` with Frontend option to generate technical architecture.
> Input: `docs/{serviceName}/spec.md` + `docs/{serviceName}/ui.md`
```

### 4-2. Save File

```
docs/{serviceName}/ui.md
```

---

## Phase 5: Completion Report

```markdown
## UI Specification Complete

### Summary
| Item | Content |
|------|---------|
| Service | {serviceName} |
| Screens | {count} screens |
| Shared Components | {count} components |

### Derived from
- Requirements: `docs/{serviceName}/spec.md`
- Backend API: `docs/{serviceName}/arch-be.md`

### Output
- Created: `docs/{serviceName}/ui.md`

### Next Steps
> Run `/arch` and select **Frontend** to generate technical architecture.
> The arch-fe skill will use this ui.md as input.
```

---

# Integration Flow

```
[spec] → docs/{serviceName}/spec.md
        ↓
[arch] (Backend) → docs/{serviceName}/arch-be.md
        ↓
[ui] → docs/{serviceName}/ui.md
        ↓
[arch] (Frontend) → docs/{serviceName}/arch-fe.md
        ↓
[build] (Frontend) → Implementation
```

---

# Important Notes

1. **Endpoint-driven derivation**
   - Every screen should map to at least one endpoint
   - Screens without endpoints may indicate missing backend features

2. **Domain patterns**
   - Use common UI patterns for the domain (e.g., e-commerce, blog, dashboard)
   - LLM has knowledge of typical UI patterns for most domains

3. **State handling is critical**
   - Every screen must define loading, empty, error, loaded states
   - This prevents UX issues in implementation

4. **ASCII wireframes are sufficient**
   - Detailed visual design is out of scope
   - Focus on component structure and hierarchy
