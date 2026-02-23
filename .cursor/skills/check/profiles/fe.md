# Frontend Check Profile

> Frontend architecture verification. Input: `arch-fe.md`.

## Component Detection Checklist

| Component | Detection Method | Triggers |
|-----------|------------------|----------|
| Component Structure | Component hierarchy defined | Prop types, Composition patterns |
| State Management | Store/Context mentioned | State scope, Persistence |
| Routing | Route definitions exist | Guards, Lazy loading |
| Form Handling | Form components mentioned | Validation, Error display |
| API Integration | API hooks/calls defined | Loading states, Error handling |
| Auth UI | Login/Auth components | Token storage, Protected routes |
| Real-time | WebSocket/SSE client | Reconnection, State sync |
| File Upload | Upload components | Progress, Validation |
| i18n | i18n mentioned | Language switching, Fallbacks |
| Theming | Dark mode, themes mentioned | Theme switching, Persistence |

## Gap Analysis Checklists

### Component Structure Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Prop types | Are all component props typed? | Suggest |
| Default props | Are defaults provided where needed? | Ask user |
| Component composition | Is composition pattern clear? | Ask user |
| Folder structure | Is component organization defined? | Suggest |
| Naming convention | Is naming pattern consistent? | Suggest |

### State Management Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Global vs Local | Is state scope clearly defined? | Ask user |
| Persistence | Should state survive refresh? | Ask user |
| Initial state | Is initial state defined? | Suggest |
| Derived state | Are selectors/computed defined? | Suggest |
| Update pattern | Is update pattern defined? | Suggest |

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

### Auth UI Gaps
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
| Virtual scrolling | Is virtualization needed? | Ask if large lists |

### Theming/Styling Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Design tokens | Are colors/spacing defined? | Ask user |
| Dark mode | Is dark mode supported? | Ask user |
| Theme persistence | Is theme preference saved? | Ask if dark mode |
| CSS strategy | Is styling approach defined? | Suggest |

## Q&A Template

```json
{
  "title": "Missing Detail: {Topic}",
  "questions": [{
    "id": "{topic_id}",
    "prompt": "{Description of missing item}. How should this be handled?",
    "options": [
      {"id": "option_a", "label": "{Option A} (recommended)"},
      {"id": "option_b", "label": "{Option B}"},
      {"id": "option_c", "label": "{Option C}"},
      {"id": "skip", "label": "Skip for now (decide during implementation)"}
    ]
  }]
}
```

Skip: Mark as `TBD` in document, continue to next gap, list all skipped at end.

## Document Update (Section 12 in arch-fe.md)

```markdown
## 12. Additional Design Details (from Review)
### State Management - Scope: {description}, Persistence: {localStorage|sessionStorage|none}
### Form Handling - Validation: {library} with {rules}, Error: {inline|toast|summary}
### UX States - Loading: {skeleton|spinner}, Error: {boundary|toast|inline}, Empty: {illustration|message}
### Accessibility - Focus: {defined|TBD}, Keyboard: {all interactive}, ARIA: {defined|TBD}
### Responsive - Breakpoints: sm({v}), md({v}), lg({v}), Mobile-first: {yes|no}
### TBD (Skipped) - {skipped item list}
```

## Summary Report

```markdown
## Frontend Architecture Review Complete
### Components Detected
- Component Structure ({N} components), State Management ({library})
- Routing ({N} routes), Form Handling ({library}), API Integration ({N} hooks)
- Authentication UI, Real-time (if detected), i18n (if detected)
### Gaps Filled: {N}
| Item | Decision |
|------|----------|
| Loading states | {skeleton} |
| Error handling | {error boundary + toast} |
| Form validation | {react-hook-form + zod} |
### Skipped (TBD): {M} - {list}
### Document Updated - docs/{serviceName}/arch-fe.md Section 12 added
### Next Step - Run `/build`
```

## Common UX Patterns Reference

### Loading States
```
Initial:          Inline:           Page:
+----------+      [Submit >]        +----------+
| ======== |                        |    o     |
| =====    |                        | Loading..|
+----------+                        +----------+
 (skeleton)       (btn spinner)     (full spinner)
```

### Error States
```
API Error:        Form Error:       Toast:
+----------+      Email             +----------+
| ! Error  |      [________]        | x Failed |
| [Retry]  |      ! Invalid email   | [Retry]  |
+----------+                        +----------+
```

### Empty States
```
No Data:          Search:
+----------+      +----------+
| (empty)  |      | No match |
| No items |      | for "x"  |
| [Create] |      | [Clear]  |
+----------+      +----------+
```
