# Frontend Pre-build Profile

## Check Categories

### 1. External Services Detection

**Parse `tech_stack.third_party` section and check:**

| Pattern | Service Type | Required Config |
|---------|--------------|-----------------|
| `oauth`, `google`, `kakao` | OAuth (Backend handles) | NEXT_PUBLIC_API_URL |
| `analytics`, `ga`, `gtag` | Google Analytics | NEXT_PUBLIC_GA_ID |
| `sentry` | Error Tracking | NEXT_PUBLIC_SENTRY_DSN |
| `hotjar`, `clarity` | Session Recording | NEXT_PUBLIC_HOTJAR_ID |
| `firebase` | Firebase | NEXT_PUBLIC_FIREBASE_* |

### 2. UI Library Setup Detection

**Parse `styling`, `ui_components` sections:**

| Pattern | Library | Init Command |
|---------|---------|--------------|
| `shadcn`, `shadcn/ui` | shadcn/ui | `npx shadcn-ui@latest init` |
| `radix` | Radix UI | npm install |
| `chakra` | Chakra UI | npm install + provider setup |
| `mui`, `material` | Material UI | npm install + theme setup |
| `ant`, `antd` | Ant Design | npm install |

### 3. Font Detection

**Parse `typography` or style sections:**

| Pattern | Font | Install Method |
|---------|------|----------------|
| `pretendard` | Pretendard | next/font/local or npm |
| `inter` | Inter | next/font/google |
| `roboto` | Roboto | next/font/google |
| `noto sans` | Noto Sans | next/font/google |

### 4. Project Bootstrap Detection

**If `project_type: new`:**

| Framework | Pattern | Init Command |
|-----------|---------|--------------|
| Next.js | `next`, `nextjs` | `npx create-next-app@latest` |
| Vite | `vite` | `npm create vite@latest` |
| CRA | `create-react-app` | `npx create-react-app` |

**Next.js Options Checklist:**
- `--typescript` (TS in tech_stack?)
- `--tailwind` (tailwind in styling?)
- `--eslint` (default yes)
- `--app` (App Router vs Pages?)
- `--src-dir` (src folder structure?)

### 5. API Mocking Detection

**If testing includes `msw`:**

- Check `src/mocks/handlers.ts` exists
- Generate handler template if missing

---

## Generated File Templates

### .env.local.example

```bash
# API
NEXT_PUBLIC_API_URL=http://localhost:8000

# Analytics (optional)
# NEXT_PUBLIC_GA_ID=

# Error Tracking (optional)
# NEXT_PUBLIC_SENTRY_DSN=
```

### shadcn/ui Init Answers Template

```
Would you like to use TypeScript? → yes
Which style would you like to use? → default
Which color would you like to use as base color? → slate
Where is your global CSS file? → src/app/globals.css
Would you like to use CSS variables for colors? → yes
Are you using a custom tailwind prefix? → (empty)
Where is your tailwind.config.js located? → tailwind.config.ts
Configure the import alias for components? → @/shared/ui
Configure the import alias for utils? → @/shared/lib
Are you using React Server Components? → yes
```

### MSW Handlers Template

```typescript
// src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const handlers = [
  // Auth
  http.get(`${API_URL}/api/v1/auth/me`, () => {
    return HttpResponse.json({
      id: 'mock-user-id',
      email: 'user@example.com',
      name: 'Mock User',
    });
  }),

  // TODO: Add more handlers based on API endpoints
];
```

### MSW Browser Setup

```typescript
// src/mocks/browser.ts
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
```

### Pretendard Font Setup (next/font/local)

```typescript
// src/app/fonts.ts
import localFont from 'next/font/local';

export const pretendard = localFont({
  src: [
    {
      path: '../fonts/Pretendard-Regular.woff2',
      weight: '400',
      style: 'normal',
    },
    {
      path: '../fonts/Pretendard-Medium.woff2',
      weight: '500',
      style: 'normal',
    },
    {
      path: '../fonts/Pretendard-SemiBold.woff2',
      weight: '600',
      style: 'normal',
    },
    {
      path: '../fonts/Pretendard-Bold.woff2',
      weight: '700',
      style: 'normal',
    },
  ],
  variable: '--font-pretendard',
});
```

### Project Init Command Template

```bash
# Next.js 14 with App Router, TypeScript, Tailwind, ESLint
npx create-next-app@latest {project-name} \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*"

# Then install additional dependencies
cd {project-name}
npm install zustand @tanstack/react-query zod react-hook-form @hookform/resolvers
npm install date-fns lucide-react
npm install -D vitest @testing-library/react playwright msw

# Initialize shadcn/ui
npx shadcn-ui@latest init
```
