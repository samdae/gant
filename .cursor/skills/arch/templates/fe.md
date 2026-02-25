# Frontend Architecture Document Template

Output: `docs/{serviceName}/arch-fe.md`
Required input: `spec.md` + `ui.md` (from /ui skill)
**NOTE**: ui.md (screens, components, states, interactions) is primary reference for Component Structure.

## Template

```markdown
# Frontend Design Doc: {Feature Name}

> Created: {date} | Service: {serviceName} | Type: Frontend
> Requirements: docs/{serviceName}/spec.md
> UI Specification: docs/{serviceName}/ui.md

## 0. Summary
### Goal
(1-2 sentences)
### Non-goals
### Success metrics

## 1. Scope
### In scope
### Out of scope

## 1.5. Tech Stack
```yaml
tech_stack:
  framework: "{framework}"                  # e.g., React 18, Next.js 14
  language: "{language}"                    # e.g., TypeScript 5.x
  state_management: "{state lib}"           # e.g., Zustand, Redux Toolkit
  styling: "{styling}"                      # e.g., Tailwind CSS
  routing: "{router}"                       # e.g., react-router v6
  api_client: "{api lib}"                   # e.g., axios, react-query
  form_handling: "{form lib}"               # e.g., react-hook-form
  build_tool: "{bundler}"                   # e.g., Vite
  testing: "{test fw}"                      # e.g., Vitest, Playwright
  third_party:
    - "{service 1}"                         # e.g., Firebase Auth
    - "{service 2}"                         # e.g., Sentry
```

## 1.6. Dependencies
```yaml
package_manager: "{npm|yarn|pnpm}"
project_type: "{new|existing}"
dependencies:
  - name: "{package}"
    version: "{version or latest}"
    purpose: "{what it's used for}"
    status: "{approved|rejected|alternative}"
```
> `status: approved` = installed in build phase.

## 2. Architecture Impact

### Component Structure
> Reference ui.md screens. Convert to technical file structure.
```yaml
component_structure:
  pages:                                    # From ui.md Screen List
    - path: "/example"
      component: "ExamplePage"
      file: "src/pages/ExamplePage.tsx"
      description: "{from ui.md}"
  features:
    - name: "{feature_name}"
      path: "src/features/{feature_name}/"
      components:
        - name: "{ComponentName}"
          type: "container | presentational"
          description: "{desc}"
  shared:
    - name: "{ComponentName}"
      path: "src/components/{ComponentName}"
      props:
        - name: "{propName}"
          type: "{type}"
          required: true
```

### File Structure
```
src/
├── pages/{PageName}/
│   ├── index.tsx
│   ├── {PageName}.tsx
│   └── {PageName}.test.tsx
├── features/{feature}/
│   ├── components/
│   ├── hooks/
│   ├── api/
│   └── types.ts
├── components/{ComponentName}/
│   ├── index.tsx
│   ├── {ComponentName}.tsx
│   ├── {ComponentName}.test.tsx
│   └── {ComponentName}.stories.tsx
├── hooks/            # Global custom hooks
├── store/            # State management
├── api/              # API layer
├── utils/
├── types/
└── styles/
```

## 3. State Management
```yaml
state_management:
  global_state:
    - name: "{storeName}"
      file: "src/store/{storeName}.ts"
      state:
        - field: "{fieldName}"
          type: "{type}"
          initial: "{value}"
      actions:
        - name: "{actionName}"
          description: "{what it does}"
      selectors:
        - name: "{selectorName}"
          returns: "{return type}"
  server_state:                             # react-query, SWR, etc.
    - query_key: "{queryKey}"
      endpoint: "{API endpoint}"
      stale_time: "{duration}"
      cache_time: "{duration}"
  local_state:
    - component: "{ComponentName}"
      states:
        - name: "{stateName}"
          type: "{type}"
          purpose: "{why}"
```

## 4. Route Definition
```yaml
routes:
  - path: "/"
    component: "HomePage"
    exact: true
    auth_required: false
  - path: "/dashboard"
    component: "DashboardPage"
    auth_required: true
    guards: ["AuthGuard"]
    children:
      - path: "settings"
        component: "SettingsPage"
  - path: "/example/:id"
    component: "ExampleDetailPage"
    params:
      - name: "id"
        type: "string"
    auth_required: true
  - path: "*"
    component: "NotFoundPage"
```

## 5. API Integration
### API Client Configuration
```yaml
api_client:
  base_url: "{API_BASE_URL}"
  timeout: 30000
  headers:
    - name: "Content-Type"
      value: "application/json"
  interceptors:
    request: ["addAuthToken", "addRequestId"]
    response: ["handleUnauthorized", "transformResponse"]
```

### API Endpoints (from arch-be.md)
```yaml
api_integration:
  - endpoint: "GET /api/v1/example"
    hook: "useExampleList"
    file: "src/features/example/api/useExampleList.ts"
    options: { stale_time: "5min", retry: 3 }
  - endpoint: "POST /api/v1/example"
    hook: "useCreateExample"
    file: "src/features/example/api/useCreateExample.ts"
    invalidates: ["exampleList"]
```

## 6. Code Mapping
| # | Spec Ref | Feature | File | Component/Hook | Props/Params | Action | Impl |
|---|----------|---------|------|----------------|--------------|--------|------|
| 1 | FR-001 | {feature} | {path} | {name} | {props} | {action} | [ ] |

> **Spec Ref**: Req ID (1:N). **Impl**: `[ ]` = pending, `[x]` = done by build.

## 7. Implementation Plan
### Required Reference Files
| File | Purpose |
|------|---------|
| {path 1} | {component patterns, naming} |
| {path 2} | {styling, design tokens} |

> Read above files first when running build skill.

### Steps
1. **Types & Interfaces** - TypeScript types, API response types
2. **API Layer** - API hooks, error handling
3. **State Management** - Stores, selectors
4. **Components** - UI components, business logic
5. **Pages & Routes** - Page components, route config

## 8. User Flow Diagram
### {Flow name}
\`\`\`mermaid
flowchart TD
    A[User Action] --> B{Route Guard}
    B -->|Authenticated| C[Page Component]
    B -->|Not Auth| D[Login Page]
    C --> E[Fetch Data]
    E --> F{Loading?}
    F -->|Yes| G[Skeleton/Spinner]
    F -->|No| H[Render Content]
    H --> I[User Interaction]
    I --> J[Update State]
    J --> K[Optimistic Update]
    K --> L[API Call]
    L -->|Success| M[Invalidate Cache]
    L -->|Error| N[Show Error Toast]
\`\`\`

## 9. Style Guide
### Design Tokens
```yaml
design_tokens:
  colors:
    primary: "{color}"                      # e.g., #3B82F6
    secondary: "{color}"                    # e.g., #6B7280
    error: "{color}"                        # e.g., #EF4444
    success: "{color}"                      # e.g., #10B981
  spacing:
    unit: "{base}"                          # e.g., 4px, 0.25rem
    scale: [1, 2, 4, 6, 8, 12, 16]
  typography:
    font_family: "{font}"                   # e.g., Inter, Pretendard
    sizes: { xs: "0.75rem", sm: "0.875rem", base: "1rem", lg: "1.125rem", xl: "1.25rem" }
  breakpoints: { sm: "640px", md: "768px", lg: "1024px", xl: "1280px" }
```

### Styling Convention
```yaml
styling_convention:
  approach: "{Tailwind | CSS Modules | styled-components}"
  naming: "{BEM | utility-first | component-scoped}"
  responsive: "{mobile-first | desktop-first}"
  dark_mode: "{supported | not supported}"
```

## 10. Risks & Tradeoffs (Debate Conclusion)
### Chosen Option
### Rejected Alternatives
### Reasoning
- Project constraints | Best practice adoption | Future improvements
### Assumptions
- **Confirmed**: {decided} | **Estimated**: {assumed, needs verification}

## 11. UX/Performance/A11y Checklist

### UX States
| State | Component | Handling | User Feedback |
|-------|-----------|----------|---------------|
| Loading | {component} | {skeleton/spinner} | {what user sees} |
| Empty | {component} | {empty state UI} | {message} |
| Error | {component} | {error boundary/toast} | {recovery action} |

### Performance
| Item | Target | Measurement | Optimization |
|------|--------|-------------|--------------|
| LCP | < 2.5s | Lighthouse | {strategy} |
| Bundle size | < {size}KB | Build output | {code splitting} |
| Re-renders | Minimal | React DevTools | {memo/useMemo} |

### Accessibility
| Item | Requirement | Implementation |
|------|-------------|----------------|
| Keyboard nav | All interactive elements | {tab order, focus} |
| Screen reader | Semantic HTML + ARIA | {aria labels, roles} |
| Color contrast | WCAG AA (4.5:1) | {contrast check} |
| Focus visible | Clear focus indicator | {focus-visible styles} |

> **WARNING**: If empty, user experience will suffer - Must complete
```
