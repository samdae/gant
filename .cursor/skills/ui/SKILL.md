---
id: ui
name: ui
description: |
  Generate UI specification from requirements and backend API design.
  Derives screen list, component hierarchy, and user interactions.
  Triggers: ui, ui spec, screen design
user-invocable: true
version: 1.0.0
triggers: ["ui", "ui spec", "screen design"]
requires: ["spec", "arch"]
platform: all
recommended_model: opus
allowed-tools: [Read, Write, Glob, LS, AskQuestion]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.

**Model**: Opus required. UI derivation needs domain knowledge and pattern matching.

# UI Workflow

Generate UI specification from requirements + backend API endpoints.

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read | Request user to copy-paste document content |
| AskQuestion | "Select: 1) A 2) B" format |

## Document Structure

```
docs/{serviceName}/
  ├── spec.md      # Input (requirements)
  ├── arch-be.md   # Input (backend API)
  └── ui.md        # ← This skill's output
```

---

## Phase -1: Service Discovery

Scan `docs/`, select service, resolve spec.md and arch-be.md paths.

## Phase 0: Skill Entry

### 0-1. Collect Document Input

If Service Discovery successful: verify spec.md and arch-be.md exist. Both exist → auto-load. Missing → guide to /spec or /arch.

If Service Discovery failed:

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

Either `no` → guide to required skill. Both `yes` → request paths → 0-1.5.

### 0-1.5. Responsive Option

```json
{
  "title": "Target Platform",
  "questions": [
    {
      "id": "responsive",
      "prompt": "What platforms are you targeting?",
      "options": [
        {"id": "mobile", "label": "Mobile only - 375px viewport"},
        {"id": "desktop", "label": "Desktop only - 1280px+"},
        {"id": "responsive", "label": "Both (Responsive) - Mobile First"}
      ]
    }
  ]
}
```

Breakpoint hints for responsive:
```yaml
breakpoints:
  mobile: "< 640px"
  tablet: "640-1024px"
  desktop: "> 1024px"
```

Record selection in ui.md header, apply to all wireframes.

### 0-2. Infer serviceName

Extract from path: `docs/blog/spec.md` → `serviceName = "blog"` → output: `docs/blog/ui.md`

### 0-3. Load Documents

Read spec.md (functional requirements) and arch-be.md (API endpoints, schemas).

---

## Phase 1: Derive Screen List

### 1-1. Analyze Endpoints

| Endpoint Pattern | Screen Derivation |
|------------------|-------------------|
| `GET /resources` | List screen |
| `GET /resources/:id` | Detail screen |
| `POST /resources` | Create form |
| `PUT /resources/:id` | Edit form |
| `DELETE /resources/:id` | Delete confirmation (modal) |
| `POST /auth/login` | Login screen |
| `POST /auth/register` | Registration screen |

### 1-2. Map Requirements to Screens

Cross-reference spec.md with derived screens. Flag screens without requirements or requirements without screens.

### 1-3. Generate Screen List

| # | Screen | Route | Related Endpoints | Auth Required | Spec Reference |
|---|--------|-------|-------------------|---------------|----------------|
| 1 | {name} | {route} | {endpoints} | Yes/No | FR-xxx |

### 1-4. User Checkpoint

> "I've derived {N} screens from the API endpoints. Please review:
>
> {Screen List Table}
>
> Should I proceed with detailed UI specifications?"

---

## Phase 2: Screen Specifications

For each screen:

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
  ui_library: "{recommended library}"
  styling: "{styling approach}"
  icons: "{icon library}"
patterns:
  layout: "{layout pattern}"          # e.g., max-w-4xl mx-auto
  spacing: "{spacing system}"         # e.g., Tailwind default scale
  typography: "{typography approach}"  # e.g., prose class for content
```

---

## Phase 4: Generate ui.md

### Template

```markdown
# UI Specification: {Feature Name}

> Created: {date}
> Service: {serviceName}
> Platform: {mobile|desktop|responsive}
> Requirements: docs/{serviceName}/spec.md
> Backend API: docs/{serviceName}/arch-be.md

## 0. Responsive Strategy
```yaml
platform: "{type}"
breakpoints:              # responsive only
  mobile: "< 640px"
  tablet: "640-1024px"
  desktop: "> 1024px"
approach: "Mobile First"
```

## 1. Screen List
| # | Screen | Route | Related Endpoints | Auth Required | Spec Reference |
|---|--------|-------|-------------------|---------------|----------------|

## 2. Screen Specifications
### 2.1 {ScreenName} ({route})
**Purpose**: {description}
**UI Components**:
```
{ASCII wireframe}
```
**Component Hierarchy**:
```yaml
{component tree}
```
**States**:
| State | Trigger | UI Behavior |
|-------|---------|-------------|
| loading | {behavior} | {detail} |
| empty | {behavior} | {detail} |
| error | {behavior} | {detail} |
| loaded | {behavior} | {detail} |

**User Interactions**:
| # | Action | Trigger | API Call | Result |
|---|--------|---------|----------|--------|

(Repeat for each screen)

## 3. Shared Components
| Component | Props | Usage |
|-----------|-------|-------|

## 4. Design System Reference
```yaml
recommendation:
  ui_library: "{lib}"
  styling: "{approach}"
  icons: "{lib}"
```

## 5. Next Steps
> Run `/arch` Frontend to generate technical architecture.
> Input: `docs/{serviceName}/spec.md` + `docs/{serviceName}/ui.md`
```

Save: `docs/{serviceName}/ui.md`

## Phase 5: Completion Report

Report: service, screen count, component count, derived-from docs. Next: run `/arch` Frontend.

---

# Integration Flow

```
[spec] → spec.md
        ↓
[arch] (Backend) → arch-be.md
        ↓
[ui] → ui.md
        ↓
[arch] (Frontend) → arch-fe.md
        ↓
[build] (Frontend) → Implementation
```

## Important Notes

1. **Endpoint-driven**: every screen maps to at least one endpoint; screens without endpoints may indicate missing backend features
2. **Domain patterns**: use common UI patterns for the domain (e-commerce, blog, dashboard, etc.)
3. **State handling**: every screen must define all 4 states (loading/empty/error/loaded)
4. **ASCII wireframes**: focus on component structure and hierarchy, not visual design
