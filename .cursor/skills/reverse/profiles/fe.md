# Frontend Reverse Engineering Profile

> This profile is for reverse-engineering frontend code.
> Use when analyzing web apps, SPAs, component libraries.

## Code Type Detection

Keywords to detect frontend code:
- `component`, `jsx`, `tsx`, `vue`, `svelte`
- `useState`, `useEffect`, `computed`, `reactive`
- `router`, `route`, `page`, `layout`
- `store`, `context`, `redux`, `zustand`, `pinia`

---

## Core File Identification

### File Type to Target Mapping

| File Type | Extraction Target | Common Patterns |
|----------|------------------|-----------------|
| **Pages/Routes** | Route structure | `pages/*.tsx`, `routes/*.vue`, `app/**/page.tsx` |
| **Components** | Component hierarchy | `components/*.tsx`, `*.vue`, `*.svelte` |
| **Hooks** | Custom logic | `hooks/*.ts`, `composables/*.ts`, `use*.ts` |
| **Store/State** | State management | `store/*.ts`, `stores/*.ts`, `*Store.ts` |
| **API Layer** | API integration | `api/*.ts`, `services/*.ts`, `queries/*.ts` |
| **Types** | Type definitions | `types/*.ts`, `*.d.ts`, `interfaces/*.ts` |
| **Styles** | Styling approach | `*.module.css`, `*.styled.ts`, `tailwind.config.js` |

### Directory Structure Patterns

```
Frontend Project Structure (React/Next.js):
├── src/ or app/
│   ├── pages/ or app/
│   ├── components/
│   │   ├── ui/           # Shared UI
│   │   └── features/     # Feature-specific
│   ├── hooks/
│   ├── store/ or context/
│   ├── api/ or services/
│   ├── types/
│   └── styles/
├── public/
└── package.json

Frontend Project Structure (Vue/Nuxt):
├── src/ or app/
│   ├── pages/ or views/
│   ├── components/
│   ├── composables/
│   ├── stores/
│   ├── api/
│   └── assets/
└── package.json
```

---

## Direct Extraction Items

### Tech Stack Extraction

| Source | What to Extract |
|--------|-----------------|
| `package.json` | Framework, state lib, styling, testing |
| `tsconfig.json` | TypeScript configuration |
| `vite.config.ts` | Build tool configuration |
| `tailwind.config.js` | Tailwind setup |
| Import statements | Libraries, patterns used |

### Framework Detection

| Indicator | Framework |
|-----------|-----------|
| `next.config.js`, `app/` folder | Next.js |
| `nuxt.config.ts`, `.nuxt/` | Nuxt |
| `vite.config.ts` + React imports | Vite + React |
| `.vue` files | Vue |
| `.svelte` files | Svelte/SvelteKit |
| `angular.json` | Angular |

### Component Structure Extraction

| Pattern | What to Extract |
|---------|----------------|
| Function components | `const Name = () => {}` |
| Props interface | `interface NameProps { }` |
| Hooks usage | `useState`, `useEffect`, custom hooks |
| Event handlers | `onClick`, `onChange`, etc. |
| Conditional rendering | Loading, error, empty states |

### Code Mapping Output Format

**All rows have `Impl = [x]` since code exists:**

| # | Feature | File | Component/Hook | Props/Params | Action | Impl |
|---|---------|------|----------------|--------------|--------|------|
| 1 | {inferred} | {path} | {component} | {key props} | {description} | [x] |

### State Management Extraction

| Library | Detection Pattern |
|---------|------------------|
| Zustand | `create()`, `useStore()` |
| Redux | `createSlice()`, `useSelector()`, `useDispatch()` |
| Pinia | `defineStore()`, `useStore()` |
| React Query | `useQuery()`, `useMutation()` |
| Context | `createContext()`, `useContext()` |

### Route Extraction

| Framework | Detection Pattern |
|-----------|------------------|
| React Router | `<Route path=`, `useNavigate()` |
| Next.js | File-based in `pages/` or `app/` |
| Vue Router | `createRouter()`, `routes: []` |
| Nuxt | File-based in `pages/` |

### API Integration Extraction

| Pattern | What to Extract |
|---------|----------------|
| `fetch()` calls | Endpoint URLs, methods |
| Axios instances | Base URL, interceptors |
| React Query hooks | Query keys, endpoints |
| API service files | All API functions |

---

## Inference Items

### Goal Inference

| Signal | Inference |
|--------|-----------|
| Dashboard components | "Admin/Management interface" |
| Form-heavy pages | "Data entry application" |
| List/Grid views | "Content browsing" |
| Chat components | "Communication feature" |
| E-commerce patterns | "Shopping experience" |

### Component Responsibility Inference

| Pattern | Inferred Responsibility |
|---------|------------------------|
| `*Page.tsx` | Route-level, data fetching |
| `*Container.tsx` | Logic, state management |
| `*View.tsx`, `*UI.tsx` | Pure presentation |
| `*Form.tsx` | Form handling |
| `*Modal.tsx` | Dialog/overlay |
| `*List.tsx`, `*Table.tsx` | Data display |

### Design System Inference

| Pattern | Inference |
|---------|-----------|
| Consistent color variables | Design tokens exist |
| Reusable Button/Input | Component library |
| Tailwind classes | Utility-first approach |
| styled-components | CSS-in-JS approach |
| CSS Modules | Scoped styling |

---

## Q&A Items (Cannot Extract)

### Required Questions

```json
{
  "questions": [
    {
      "id": "app_purpose",
      "prompt": "What is the main purpose of this application?",
      "type": "open"
    },
    {
      "id": "users",
      "prompt": "Who are the primary users?",
      "options": [
        {"id": "internal", "label": "Internal team/employees"},
        {"id": "b2b", "label": "Business customers (B2B)"},
        {"id": "b2c", "label": "End users (B2C)"},
        {"id": "mixed", "label": "Both internal and external"}
      ]
    },
    {
      "id": "design_system",
      "prompt": "Is there a design system or style guide?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide reference"},
        {"id": "no", "label": "No - Use extracted patterns"},
        {"id": "partial", "label": "Partially documented"}
      ]
    },
    {
      "id": "critical_flow",
      "prompt": "What is the most important user flow?",
      "type": "open"
    }
  ]
}
```

---

## Output Templates

### spec.md Output Sections

```markdown
# Requirements (Reverse-engineered)

> ⚠️ Reverse-engineered from code. Verify with stakeholders.

## 1. Overview
- Service Name: {extracted}
- Domain: {inferred}
- Development Focus: [x] Frontend

## 2. Purpose
- Goal: {inferred from UI patterns} ❓
- Non-goals: {from Q&A}

## 3. Feature Specifications
| Feature | Description | Confidence |
|---------|-------------|------------|
| {from routes/pages} | {inferred} | High/Medium/Low |

## 4. Data Contracts
| Entity | Fields | Source |
|--------|--------|--------|
| {from types} | {extracted} | Code |

## 5. User Flows
{inferred from route structure and components}
```

### arch-fe.md Output Sections

```markdown
# Frontend Design Doc (Reverse-engineered)

> ⚠️ Extracted from existing code.
> - **Extracted**: Component Structure, Routes, State (reliable)
> - **Inferred**: User flows, Design intent (verify needed)

## 1.5. Tech Stack
{extracted from package.json}

## 2. Architecture Impact
### Component Structure
{extracted from file analysis}

## 3. State Management
{extracted from store files}

## 4. Route Definition
{extracted from router config or file structure}

## 5. API Integration
{extracted from API layer}
```

---

## Component Analysis Template

For each component, extract:

```markdown
### ComponentName

- **File**: `src/components/ComponentName.tsx`
- **Type**: Page | Container | Presentational | Form
- **Props**:
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | {prop} | {type} | {yes/no} | {inferred} |
- **State**:
  - Local: {useState hooks}
  - Global: {store connections}
- **API Calls**: {hooks or fetch calls}
- **Child Components**: {list}
```

---

## Completeness Indicators

| Section | Status | Meaning |
|---------|--------|---------|
| ✅ Extracted | Reliable | Directly from code |
| ❓ Inferred | Verify | Guessed from patterns |
| ❌ Unknown | Required | Need human input |
