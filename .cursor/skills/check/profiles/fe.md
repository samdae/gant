# Frontend Check Profile

> This profile is for frontend architecture verification.
> Use when input is `arch-fe.md`.

## Input Detection

- Input file: `arch-fe.md`
- Applies automatically when design document is frontend-focused

---

## Component Detection Checklist

Scan the design document and detect which components are defined:

| Component | Detection Method | Triggers Additional Checks |
|-----------|-----------------|---------------------------|
| **Component Structure** | Component hierarchy defined | Prop types, Composition patterns |
| **State Management** | Store/Context mentioned | State scope, Persistence |
| **Routing** | Route definitions exist | Guards, Lazy loading |
| **Form Handling** | Form components mentioned | Validation, Error display |
| **API Integration** | API hooks/calls defined | Loading states, Error handling |
| **Authentication UI** | Login/Auth components | Token storage, Protected routes |
| **Real-time** | WebSocket/SSE client | Reconnection, State sync |
| **File Upload** | Upload components | Progress, Validation |
| **Internationalization** | i18n mentioned | Language switching, Fallbacks |
| **Theming** | Dark mode, themes mentioned | Theme switching, Persistence |

---

## Gap Analysis Checklists

### Component Structure Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Prop types defined | Are all component props typed? | Suggest |
| Default props | Are defaults provided where needed? | Ask user |
| Component composition | Is composition pattern clear? | Ask user |
| Folder structure | Is component organization defined? | Suggest |
| Naming convention | Is naming pattern consistent? | Suggest |

### State Management Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Global vs Local state | Is state scope clearly defined? | Ask user |
| State persistence | Should state survive refresh? | Ask user |
| State initialization | Is initial state defined? | Suggest |
| Derived state | Are selectors/computed defined? | Suggest |
| State updates | Is update pattern defined? | Suggest |

### Routing Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Route guards | Are protected routes defined? | Ask user |
| 404 handling | Is not-found route defined? | Suggest |
| Lazy loading | Are routes code-split? | Suggest |
| Route params | Are dynamic params typed? | Suggest |
| Breadcrumbs | Is navigation context needed? | Ask if complex |

### Form Handling Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Validation rules | Is form validation defined? | Ask user |
| Error display | How are errors shown? | Ask user |
| Submit handling | Is submit flow defined? | Ask user |
| Loading states | Is submit loading shown? | Suggest |
| Success feedback | Is success message defined? | Ask user |
| Form reset | When to reset form? | Ask user |

### API Integration Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Loading states | Is loading UI defined? | Ask user |
| Error handling | Is error UI defined? | Ask user |
| Empty states | Is empty data UI defined? | Ask user |
| Retry mechanism | Can user retry failed calls? | Suggest |
| Caching strategy | Is data caching defined? | Ask user |
| Optimistic updates | Are updates optimistic? | Ask if needed |
| Polling/Refresh | Is auto-refresh needed? | Ask if real-time |

### Authentication UI Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Token storage | Where is token stored? | Ask user |
| Protected routes | Are auth guards defined? | Ask user |
| Login redirect | Where to redirect after login? | Ask user |
| Session expiry | How to handle expired session? | Ask user |
| Logout flow | Is logout behavior defined? | Ask user |

### UX States Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Loading skeleton | Is skeleton UI defined? | Suggest |
| Error boundary | Is error fallback defined? | Suggest |
| Empty state | Is empty state UI defined? | Ask user |
| Success feedback | Is success toast/message defined? | Ask user |
| Confirmation dialogs | Are destructive actions confirmed? | Ask user |

### Accessibility Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Keyboard navigation | Are all elements keyboard accessible? | Suggest |
| Focus management | Is focus trap defined for modals? | Suggest |
| ARIA labels | Are interactive elements labeled? | Suggest |
| Color contrast | Is WCAG AA compliance met? | Ask user |
| Screen reader | Are announcements defined? | Ask if needed |

### Responsive Design Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Breakpoints | Are breakpoints defined? | Ask user |
| Mobile layout | Is mobile layout specified? | Ask user |
| Touch targets | Are touch targets 44px+? | Suggest |
| Orientation | Is landscape handled? | Ask if mobile |

### Performance Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Code splitting | Are large components lazy loaded? | Suggest |
| Image optimization | Are images optimized? | Suggest |
| Memoization | Are expensive renders memoized? | Suggest |
| Bundle size | Is bundle size tracked? | Suggest |
| Virtual scrolling | Is virtualization needed for lists? | Ask if large lists |

### Theming/Styling Gaps

| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Design tokens | Are colors/spacing defined? | Ask user |
| Dark mode | Is dark mode supported? | Ask user |
| Theme persistence | Is theme preference saved? | Ask if dark mode |
| CSS strategy | Is styling approach defined? | Suggest |

---

## Q&A Templates

### Choice-based Question

```json
{
  "title": "Missing Detail: {Topic}",
  "questions": [
    {
      "id": "{topic_id}",
      "prompt": "{Description of missing item}. How should this be handled?",
      "options": [
        {"id": "option_a", "label": "{Option A} (recommended)"},
        {"id": "option_b", "label": "{Option B}"},
        {"id": "option_c", "label": "{Option C}"},
        {"id": "skip", "label": "Skip for now (decide during implementation)"}
      ]
    }
  ]
}
```

### Skip Handling

If user selects "Skip for now":
- Mark as `⚠️ TBD` in document
- Continue to next gap
- List all skipped items at the end

---

## Document Update Location

Add new section or update existing sections in `arch-fe.md`:

```markdown
## 12. Additional Design Details (from Review)

### State Management Details
- Global state scope: {description}
- Persistence: {localStorage | sessionStorage | none}
- Initial state: {defined | TBD}

### Form Handling Details
- Validation: {library} with {rules}
- Error display: {inline | toast | summary}
- Submit loading: {button disabled | spinner}

### UX State Details
- Loading: {skeleton | spinner}
- Error: {error boundary | toast | inline}
- Empty: {illustration | message}

### Accessibility Details
- Focus management: {defined | TBD}
- Keyboard navigation: {all interactive elements}
- ARIA labels: {defined | TBD}

### Responsive Details
- Breakpoints: sm({value}), md({value}), lg({value})
- Mobile-first: {yes | no}

### ⚠️ TBD (Skipped)
- {skipped item 1}
- {skipped item 2}
```

---

## Summary Report Template

```markdown
## Frontend Architecture Review Complete

### Components Detected
- ✅ Component Structure ({component count} components)
- ✅ State Management ({library})
- ✅ Routing ({route count} routes)
- ✅ Form Handling ({library})
- ✅ API Integration ({hook count} hooks)
- ⬜ Real-time (not detected)
- ✅ Authentication UI
- ⬜ Internationalization (not detected)

### Gaps Filled: {N}
| Item | Decision |
|------|----------|
| Loading states | {skeleton} |
| Error handling | {error boundary + toast} |
| Form validation | {react-hook-form + zod} |

### Skipped (TBD): {M}
- {skipped item 1}
- {skipped item 2}

### Document Updated
`docs/{serviceName}/arch-fe.md` - Section 12 added

### Next Step
Run `/build` to start implementation.
```

---

## Common UX Patterns Reference

### Loading States

```
Initial Load:
┌─────────────────────┐
│ ████████████████    │  ← Skeleton
│ ████████            │
│ ████████████        │
└─────────────────────┘

Inline Action:
[Submit ↻] ← Spinner in button

Page Transition:
┌─────────────────────┐
│        ◌            │  ← Full page spinner
│     Loading...      │
└─────────────────────┘
```

### Error States

```
API Error:
┌─────────────────────┐
│ ⚠️ Something went   │
│    wrong            │
│ [Retry] [Go Back]   │
└─────────────────────┘

Form Error:
┌─────────────────────┐
│ Email               │
│ [________________]  │
│ ⚠️ Invalid email    │  ← Inline error
└─────────────────────┘

Toast:
┌─────────────────────┐
│ ❌ Failed to save   │
│    [Retry]     [×]  │
└─────────────────────┘
```

### Empty States

```
No Data:
┌─────────────────────┐
│        📭           │
│   No items yet      │
│  [Create First]     │
└─────────────────────┘

Search No Results:
┌─────────────────────┐
│        🔍           │
│ No results for      │
│ "search term"       │
│ [Clear Search]      │
└─────────────────────┘
```
