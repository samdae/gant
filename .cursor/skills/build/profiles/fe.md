# Frontend Build Profile

> Input: `arch-fe.md`. Applies automatically for frontend design documents.

---

## Package Installation (Phase 0.5)

| Manager | Install | Dev Install | Lock File |
|---------|---------|-------------|-----------|
| npm | `npm install {pkg}` | `npm install -D {pkg}` | `package-lock.json` |
| yarn | `yarn add {pkg}` | `yarn add -D {pkg}` | `yarn.lock` |
| pnpm | `pnpm add {pkg}` | `pnpm add -D {pkg}` | `pnpm-lock.yaml` |

**NOTE**: Distinguish runtime vs devDependencies:
- Runtime: react, react-dom, axios, zustand, etc.
- Dev: typescript, @types/react, vite, eslint, prettier, etc.

**New projects**: Initialize first (`npm init`, etc.), then install.
**Existing projects**: Check package.json, install only new packages.

---

## Project Settings Questions

Ask only what wasn't auto-detected from Tech Stack:

```json
{
  "title": "Frontend Project Settings",
  "questions": [
    {
      "id": "framework",
      "prompt": "Frontend framework?",
      "options": [
        {"id": "react", "label": "React (CRA, Vite)"},
        {"id": "nextjs", "label": "Next.js"},
        {"id": "vue", "label": "Vue 3"},
        {"id": "nuxt", "label": "Nuxt"},
        {"id": "angular", "label": "Angular"},
        {"id": "svelte", "label": "Svelte / SvelteKit"},
        {"id": "other", "label": "Other (specify)"}
      ]
    },
    {
      "id": "state_management",
      "prompt": "State management?",
      "options": [
        {"id": "zustand", "label": "Zustand"},
        {"id": "redux", "label": "Redux / Redux Toolkit"},
        {"id": "pinia", "label": "Pinia (Vue)"},
        {"id": "jotai", "label": "Jotai"},
        {"id": "context", "label": "React Context only"},
        {"id": "none", "label": "No global state"},
        {"id": "other", "label": "Other (specify)"}
      ]
    },
    {
      "id": "styling",
      "prompt": "Styling approach?",
      "options": [
        {"id": "tailwind", "label": "Tailwind CSS"},
        {"id": "styled", "label": "styled-components / Emotion"},
        {"id": "css_modules", "label": "CSS Modules"},
        {"id": "scss", "label": "SCSS / Sass"},
        {"id": "vanilla", "label": "Vanilla CSS"},
        {"id": "other", "label": "Other (specify)"}
      ]
    },
    {
      "id": "api_client",
      "prompt": "API calls?",
      "options": [
        {"id": "react_query", "label": "TanStack Query (React Query)"},
        {"id": "swr", "label": "SWR"},
        {"id": "rtk_query", "label": "RTK Query"},
        {"id": "axios", "label": "Axios (manual)"},
        {"id": "fetch", "label": "Fetch API (manual)"},
        {"id": "other", "label": "Other (specify)"}
      ]
    },
    {
      "id": "form_handling",
      "prompt": "Form handling?",
      "options": [
        {"id": "react_hook_form", "label": "React Hook Form"},
        {"id": "formik", "label": "Formik"},
        {"id": "vee_validate", "label": "VeeValidate (Vue)"},
        {"id": "native", "label": "Native / Manual"},
        {"id": "other", "label": "Other (specify)"}
      ]
    },
    {
      "id": "commit_strategy",
      "prompt": "Git commit strategy?",
      "options": [
        {"id": "none", "label": "No commit (default)"},
        {"id": "per_phase", "label": "Commit per step"},
        {"id": "final", "label": "Commit once after completion"}
      ]
    },
    {
      "id": "test_strategy",
      "prompt": "Test code writing?",
      "options": [
        {"id": "per_component", "label": "Write test per component"},
        {"id": "per_design", "label": "Only when in design doc"},
        {"id": "none", "label": "No test writing"}
      ]
    },
    {
      "id": "storybook",
      "prompt": "Use Storybook?",
      "options": [
        {"id": "yes", "label": "Yes - Create stories for new components"},
        {"id": "no", "label": "No - Skip Storybook"}
      ]
    }
  ]
}
```

- "other" selected -> Request specific package name

---

## Dependency Graph

```
0. shared/common (first) - utilities, constants, shared types
1. Types/Interfaces (independent) - TS types, API response types, prop types
2. API Layer (depends on Types) - API client, data fetching hooks, error utils
3. Store/State (depends on Types) - global state, actions, selectors
4. Shared Components (depends on Types, may depend on Store) - reusable UI, design system, forms
5. Feature Components (depends on API, Store, Shared) - feature-specific, container, business logic
6. Pages/Routes (depends on Feature Components) - page-level, route config, layouts
```

### Parallel Execution Rules

| Step | Can Parallel With | Reason |
|------|-------------------|--------|
| Types + Shared Components (basic) | Yes | No dependencies |
| API Layer + Store | Yes | Both depend only on Types |
| Feature Components | After API, Store, Shared | Multiple dependencies |
| Pages/Routes | After Feature Components | Depends on all |

> Execute sequentially when modifying same file to prevent conflicts

---

## Sub-agent Prompt Template

```
## Implementation Task

### Step Information
- Step name: {from Implementation Plan}
- Goal: {step description}

### Tech Stack
- Framework: {framework}
- Language: TypeScript
- State Management: {state lib}
- Styling: {styling approach}
- API Client: {api client}

### Code Mapping (files to handle in this step)
| # | Feature | File | Component/Hook | Props/Params | Action | Impl |
|---|---------|------|----------------|--------------|--------|------|
| {#} | {feature} | {file path} | {component or hook name} | {key props} | {what to implement} | [ ] |

**WARNING**: Only implement rows where `Impl = [ ]`
**WARNING**: Follow existing component patterns in the project

### Design Spec
{Component Structure, State Management, Route Definition from arch-fe.md}

### Already Created Files
{list from previous steps}

### Required Reference Patterns
**Reference File**: {path}
**Patterns to Apply**:
- Component structure: {folder structure, file naming}
- Styling approach: {className patterns, CSS conventions}
- State patterns: {how state is managed}
- Error handling: {error boundary, toast patterns}

### Project Settings
- Test: {test_strategy}
- Storybook: {storybook setting}
- Commit: {commit_strategy}

### Implementation Rules (Must Follow)

**1. Read Existing File First (Top Priority)**
- If target file exists, **must Read entire content first**
- For new files, **Read at least 1 similar component** in same directory
- No Write/Edit without reading first

**2. Search and Replicate Similar Component Patterns**
- **Grep for similar components** in project
- **Replicate folder structure, naming, styling** of found patterns

**3. Component Rules**
- TypeScript for all files
- Define Props interface for all components
- Handle loading, error, empty states
- Follow project's styling convention

**4. General Rules**
- Auto-fix lint errors (max 3 attempts)
- Ensure no TypeScript errors
- Return list of created/modified files

**5. Update Implementation Status (IMPORTANT)**
- After implementing each Code Mapping row:
  1. Read design doc (arch-fe.md)
  2. Find row by `#` in Code Mapping table
  3. Update `[ ]` -> `[x]` via StrReplace

### Return Format
- created_files: [paths]
- modified_files: [paths]
- impl_updated: [# numbers updated to [x]]
- status: success | failed
- error: (if failed)
```

---

## Component Boilerplate Reference

### Basic Component (FC with loading state)

```tsx
import { FC } from 'react';
import styles from './ExampleComponent.module.css';

interface ExampleComponentProps {
  title: string;
  onAction?: () => void;
  isLoading?: boolean;
}

export const ExampleComponent: FC<ExampleComponentProps> = ({
  title, onAction, isLoading = false,
}) => {
  if (isLoading) {
    return <div className={styles.skeleton}>Loading...</div>;
  }
  return (
    <div className={styles.container}>
      <h2>{title}</h2>
      {onAction && <button onClick={onAction}>Action</button>}
    </div>
  );
};
```

### API Hook (useQuery)

```tsx
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { Example } from '@/types/example';

export const useExampleList = (params?: { page?: number }) => {
  return useQuery({
    queryKey: ['examples', params],
    queryFn: async () => {
      const response = await apiClient.get<Example[]>('/api/v1/examples', { params });
      return response.data;
    },
    staleTime: 5 * 60 * 1000,
  });
};
```

### Store (Zustand)

```tsx
import { create } from 'zustand';

interface ExampleState {
  items: string[];
  addItem: (item: string) => void;
  removeItem: (item: string) => void;
  reset: () => void;
}

export const useExampleStore = create<ExampleState>((set) => ({
  items: [],
  addItem: (item) => set((state) => ({ items: [...state.items, item] })),
  removeItem: (item) => set((state) => ({
    items: state.items.filter((i) => i !== item)
  })),
  reset: () => set({ items: [] }),
}));
```

---

## Completion Report Template

```markdown
## Implementation Completion Report

### Execution Summary
| Step | Status | Created Files | Modified Files |
|------|--------|--------------|---------------|
| 1. Types | OK | {count} | {count} |
| 2. API Layer | OK | {count} | {count} |
| 3. Store | OK | {count} | {count} |
| 4. Shared Components | OK | {count} | {count} |
| 5. Feature Components | OK | {count} | {count} |
| 6. Pages/Routes | OK | {count} | {count} |

### Created Files
- `src/types/{name}.ts` - Type definitions
- `src/api/{name}.ts` - API hooks
- `src/components/{Name}/` - Component folder

### Modified Files
- `src/routes/index.tsx` - Added new routes
- `src/store/index.ts` - Exported new store

### Environment Variables
(If API endpoints or feature flags added)
\`\`\`env
VITE_API_BASE_URL=https://api.example.com
VITE_FEATURE_FLAG=true
\`\`\`

### Build Verification
\`\`\`bash
npm run type-check  # or tsc --noEmit
npm run lint
npm run build
\`\`\`

### Remaining Manual Tasks
- [ ] Environment variable setup (.env.local)
- [ ] Run tests: `npm run test`
- [ ] Visual verification in browser
- [ ] Responsive design check
- [ ] Accessibility check (keyboard navigation, screen reader)

### Git Commit
(Based on commit strategy) Committed / Not committed

### Next Steps Guide
> **Implementation Complete**
> If bugs occur, run `debug` skill.
> Document paths: `docs/{serviceName}/spec.md`, `arch-fe.md`
> **Recommended checks:** Storybook: `npm run storybook`, E2E: `npm run test:e2e`
```
