# Frontend Reverse Engineering Profile

> Reverse-engineering frontend code. Use for web apps, SPAs, component libraries.

## Code Type Detection

Keywords: component, jsx, tsx, vue, svelte, useState, useEffect, computed, reactive, router, route, page, layout, store, context, redux, zustand, pinia

## Core File Identification

### File Type to Target Mapping

| File Type | Extraction Target | Common Patterns |
|----------|-------------------|-----------------|
| Pages/Routes | Route structure | `pages/*.tsx`, `routes/*.vue`, `app/**/page.tsx` |
| Components | Component hierarchy | `components/*.tsx`, `*.vue`, `*.svelte` |
| Hooks | Custom logic | `hooks/*.ts`, `composables/*.ts`, `use*.ts` |
| Store/State | State management | `store/*.ts`, `stores/*.ts`, `*Store.ts` |
| API Layer | API integration | `api/*.ts`, `services/*.ts`, `queries/*.ts` |
| Types | Type definitions | `types/*.ts`, `*.d.ts`, `interfaces/*.ts` |
| Styles | Styling approach | `*.module.css`, `*.styled.ts`, `tailwind.config.js` |

### Directory Structure

```
React/Next: src/ or app/
├── pages/ or app/
├── components/ (ui/, features/)
├── hooks/
├── store/ or context/
├── api/ or services/
├── types/
└── styles/

Vue/Nuxt: src/ or app/
├── pages/ or views/
├── components/
├── composables/
├── stores/
├── api/
└── assets/
```

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

### Code Mapping Output

All rows have `Impl = [x]` since code exists:

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
| React Router | `<Route path="..." />`, `createBrowserRouter` |
| Next.js App | `app/**/page.tsx` file structure |
| Next.js Pages | `pages/**/*.tsx` file structure |
| Vue Router | `routes: [{ path, component }]` |
| Nuxt | `pages/**/*.vue` file structure |

## Q&A Items (Cannot Extract)

```json
{
  "questions": [
    {"id": "app_purpose", "prompt": "What is the main purpose of this application?", "type": "open"},
    {"id": "users", "prompt": "Who are the primary users?",
      "options": [
        {"id": "internal", "label": "Internal team/employees"},
        {"id": "b2b", "label": "Business customers (B2B)"},
        {"id": "b2c", "label": "End users (B2C)"},
        {"id": "mixed", "label": "Both internal and external"}
      ]},
    {"id": "design_system", "prompt": "Is there a design system or style guide?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide reference"},
        {"id": "no", "label": "No - Use extracted patterns"},
        {"id": "partial", "label": "Partially documented"}
      ]},
    {"id": "critical_flow", "prompt": "What is the most important user flow?", "type": "open"}
  ]
}
```

## Output Templates

**spec.md:**
```markdown
# Requirements (Reverse-engineered)
> Reverse-engineered from code. Verify with stakeholders.
## 1. Overview
- Service Name: {extracted}, Domain: {inferred}, Focus: [x] Frontend
## 2. Purpose
- Goal: {inferred from UI patterns} [verify], Non-goals: {from Q&A}
## 3. Feature Specifications
| Feature | Description | Confidence |
|---------|-------------|------------|
| {from routes/pages} | {inferred} | High/Medium/Low |
## 4. Data Contracts
| Entity | Fields | Source |
|--------|--------|--------|
| {from types} | {extracted} | Code |
## 5. User Flows - {inferred from route structure and components}
```

**arch-fe.md:**
```markdown
# Frontend Design Doc (Reverse-engineered)
> Extracted from existing code.
> - Extracted (reliable): Component Structure, Routes, State, API Integration
> - Inferred (verify needed): User flows, Design intent
## 1.5. Tech Stack - {extracted from package.json}
## 2. Architecture Impact - Component Structure {from file analysis}
## 3. State Management - {extracted from store files}
## 4. Route Definition - {extracted from router config or file structure}
## 5. API Integration - {extracted from API layer}
```

**Component Card Template:**
```markdown
### ComponentName
- File: `src/components/ComponentName.tsx`
- Type: Page | Container | Presentational | Form
- Props:
  | Name | Type | Required | Description |
  |------|------|----------|-------------|
  | {prop} | {type} | {yes/no} | {inferred} |
- State: Local {useState hooks}, Global {store connections}
- API Calls: {hooks or fetch calls}
- Child Components: {list}
```

## Completeness Indicators

| Section | Status | Meaning |
|---------|--------|---------|
| Extracted | Reliable | Directly from code |
| Inferred [verify] | Verify needed | Guessed from patterns |
| Unknown [required] | Required | Need human input |
