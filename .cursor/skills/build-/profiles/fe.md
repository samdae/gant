# Frontend Build Profile

> This profile is for frontend implementation.
> Use when input is `arch-fe.md`.

## Input Detection

- Input file: `arch-fe.md`
- Applies automatically when design document is frontend-focused

---

## Package Installation (Phase 0.5)

**Frontend-specific package managers:**

| Manager | Install Command | Lock File | Dev Dependencies |
|---------|-----------------|-----------|------------------|
| npm | `npm install` | `package-lock.json` | `npm install -D` |
| yarn | `yarn install` | `yarn.lock` | `yarn add -D` |
| pnpm | `pnpm install` | `pnpm-lock.yaml` | `pnpm add -D` |

**For new projects (project_type: new):**
1. Initialize project if needed (`npm init`, `yarn init`, etc.)
2. Install packages from Dependencies section

**For existing projects (project_type: existing):**
1. Check package.json for already installed packages
2. Install only new packages

**Example commands:**
```bash
# npm
npm install react react-dom zustand axios
npm install -D typescript @types/react vite

# yarn
yarn add react react-dom zustand axios
yarn add -D typescript @types/react vite

# pnpm
pnpm add react react-dom zustand axios
pnpm add -D typescript @types/react vite
```

**Note**: Distinguish between runtime dependencies and devDependencies:
- Runtime: react, axios, zustand, etc.
- Dev: typescript, vite, eslint, prettier, etc.

---

## Project Settings Questions

```json
{
  "title": "Frontend Project Settings",
  "questions": [
    {
      "id": "framework",
      "prompt": "What frontend framework are you using?",
      "options": [
        {"id": "react", "label": "React (Create React App, Vite)"},
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
      "prompt": "What state management do you use?",
      "options": [
        {"id": "zustand", "label": "Zustand"},
        {"id": "redux", "label": "Redux / Redux Toolkit"},
        {"id": "pinia", "label": "Pinia (Vue)"},
        {"id": "jotai", "label": "Jotai"},
        {"id": "context", "label": "React Context only"},
        {"id": "none", "label": "No global state management"},
        {"id": "other", "label": "Other (specify)"}
      ]
    },
    {
      "id": "styling",
      "prompt": "What styling approach do you use?",
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
      "prompt": "How do you handle API calls?",
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
      "prompt": "How do you handle forms?",
      "options": [
        {"id": "react_hook_form", "label": "React Hook Form"},
        {"id": "formik", "label": "Formik"},
        {"id": "vee_validate", "label": "VeeValidate (Vue)"},
        {"id": "native", "label": "Native / Manual handling"},
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
        {"id": "per_design", "label": "Only when specified in design document"},
        {"id": "none", "label": "No test writing"}
      ]
    },
    {
      "id": "storybook",
      "prompt": "Do you use Storybook for component documentation?",
      "options": [
        {"id": "yes", "label": "Yes - Create stories for new components"},
        {"id": "no", "label": "No - Skip Storybook"}
      ]
    }
  ]
}
```

**Additional questions:**
- When "other" selected → Request specific package name

---

## Dependency Graph

Frontend implementation follows this dependency order:

```
0. shared/common (first)
   └── Utility functions, constants, types shared across modules

1. Types/Interfaces (independent)
   └── TypeScript type definitions
   └── API response types
   └── Component prop types

2. API Layer (depends on Types)
   └── API client setup
   └── Custom hooks for data fetching
   └── Error handling utilities

3. Store/State (depends on Types)
   └── Global state stores
   └── Actions and selectors
   └── State persistence (if any)

4. Shared Components (depends on Types, may depend on Store)
   └── Reusable UI components
   └── Design system components
   └── Form components

5. Feature Components (depends on API, Store, Shared Components)
   └── Feature-specific components
   └── Container components
   └── Business logic components

6. Pages/Routes (depends on Feature Components)
   └── Page-level components
   └── Route configuration
   └── Layout components
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

## Completion Report Template

```markdown
## Implementation Completion Report

### Execution Summary
| Step | Status | Created Files | Modified Files |
|------|--------|--------------|---------------|
| 1. Types | ✅ | {count} | {count} |
| 2. API Layer | ✅ | {count} | {count} |
| 3. Store | ✅ | {count} | {count} |
| 4. Shared Components | ✅ | {count} | {count} |
| 5. Feature Components | ✅ | {count} | {count} |
| 6. Pages/Routes | ✅ | {count} | {count} |

### Created Files
- `src/types/{name}.ts` - Type definitions
- `src/api/{name}.ts` - API hooks
- `src/components/{Name}/` - Component folder

### Modified Files
- `src/routes/index.tsx` - Added new routes
- `src/store/index.ts` - Exported new store

### Environment Variables
(If API endpoints or feature flags added)
```env
VITE_API_BASE_URL=https://api.example.com
VITE_FEATURE_FLAG=true
```

### Build Verification
```bash
# Type check
npm run type-check  # or tsc --noEmit

# Lint check
npm run lint

# Build test
npm run build
```

### Remaining Manual Tasks
- [ ] Environment variable setup (.env.local)
- [ ] Run tests: `npm run test`
- [ ] Visual verification in browser
- [ ] Responsive design check
- [ ] Accessibility check (keyboard navigation, screen reader)

### Git Commit
(Based on commit strategy)
- Committed / Not committed

### Next Steps Guide
> ✅ **Implementation Complete**
>
> If bugs occur, run `debug` skill in **Debug mode**.
> Document paths: `docs/{serviceName}/spec.md`, `arch-fe.md`
>
> **Recommended checks:**
> - Run Storybook: `npm run storybook`
> - Run E2E tests: `npm run test:e2e`
```

---

## Sub-agent Prompt Template

When invoking sub-agent for each step:

```
## Implementation Task

### Step Information
- Step name: {extracted from Implementation Plan}
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

⚠️ Only implement rows where `Impl = [ ]`
⚠️ Follow existing component patterns in the project

### Design Spec
{Component Structure, State Management, Route Definition from arch-fe.md}

### Already Created Files (for reference)
{list of files created in previous steps}

### Required Reference Patterns
**Reference File**: {required reference file path}
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

#### 1. Read Existing File First (Top Priority)
- If target file to modify already exists, **must first Read entire content**
- Even for new files, **Read at least 1 similar component** in same directory
- No Write/Edit without reading first

#### 2. Search and Replicate Similar Component Patterns
- **Search for similar components with Grep** in project
- **Replicate folder structure, naming, styling approach** of found patterns
- Example: When adding Button → Check existing Button components

#### 3. Component Rules
- Use TypeScript for all files
- Define Props interface for all components
- Handle loading, error, empty states
- Follow project's styling convention

#### 4. General Rules
- Auto-fix lint errors (max 3 attempts)
- Ensure no TypeScript errors
- Return list of created/modified files upon completion

#### 5. Update Implementation Status (IMPORTANT)
- After successfully implementing each Code Mapping row:
  1. Read the design document (arch-fe.md)
  2. Find the row by `#` number in Code Mapping table
  3. Update `[ ]` → `[x]` using StrReplace
  - Example: `| 3 | Dashboard | ... | [ ] |` → `| 3 | Dashboard | ... | [x] |`

### Return Format
Report upon completion:
- created_files: [created file paths]
- modified_files: [modified file paths]
- impl_updated: [list of # numbers updated to [x]]
- status: success | failed
- error: (error content if failed)
```

---

## Component Boilerplate Reference

### Basic Component Structure

```tsx
// src/components/ExampleComponent/ExampleComponent.tsx
import { FC } from 'react';
import styles from './ExampleComponent.module.css'; // or use Tailwind

interface ExampleComponentProps {
  title: string;
  onAction?: () => void;
  isLoading?: boolean;
}

export const ExampleComponent: FC<ExampleComponentProps> = ({
  title,
  onAction,
  isLoading = false,
}) => {
  if (isLoading) {
    return <div className={styles.skeleton}>Loading...</div>;
  }

  return (
    <div className={styles.container}>
      <h2>{title}</h2>
      {onAction && (
        <button onClick={onAction}>Action</button>
      )}
    </div>
  );
};
```

### API Hook Structure

```tsx
// src/features/example/api/useExampleList.ts
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/api/client';
import type { Example } from '@/types/example';

export const useExampleList = (params?: { page?: number }) => {
  return useQuery({
    queryKey: ['examples', params],
    queryFn: async () => {
      const response = await apiClient.get<Example[]>('/api/v1/examples', {
        params,
      });
      return response.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
```

### Store Structure (Zustand example)

```tsx
// src/store/exampleStore.ts
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
