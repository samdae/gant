# Frontend Test Profile

This profile defines test generation patterns for frontend (E2E) testing using Playwright.

## Test Framework: Playwright

Playwright is the default E2E testing framework for frontend tests.

### Installation Check

```bash
# Check if Playwright is installed
grep -q "playwright" package.json && echo "Installed" || echo "Not installed"
```

### Installation Command

```bash
# Install Playwright
npm install -D @playwright/test

# Install browsers
npx playwright install
```

## Test File Naming Convention

| Source File | Test File |
|-------------|-----------|
| `src/pages/alerts/index.tsx` | `e2e/alerts.spec.ts` |
| `src/pages/alerts/[id].tsx` | `e2e/alert-detail.spec.ts` |
| `src/components/AlertList.tsx` | `e2e/components/alert-list.spec.ts` |

## Test Structure Template

### Page Test

```typescript
import { test, expect } from '@playwright/test';

test.describe('{PageName} Page - {FR_IDs}', () => {
  test.beforeEach(async ({ page }) => {
    // Setup: login, navigate, etc.
    await page.goto('/{route}');
  });

  // State: Loading
  test('should show loading state initially', async ({ page }) => {
    // Mock slow API response
    await page.route('**/api/{resource}', async route => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      await route.fulfill({ json: [] });
    });
    
    await page.goto('/{route}');
    await expect(page.getByTestId('loading-spinner')).toBeVisible();
  });

  // State: Loaded (with data)
  test('should display {resource} list', async ({ page }) => {
    await expect(page.getByRole('heading', { name: '{PageTitle}' })).toBeVisible();
    await expect(page.getByTestId('{resource}-list')).toBeVisible();
  });

  // State: Empty
  test('should show empty state when no data', async ({ page }) => {
    await page.route('**/api/{resource}', route => 
      route.fulfill({ json: [] })
    );
    await page.goto('/{route}');
    await expect(page.getByText('No {resource} found')).toBeVisible();
  });

  // State: Error
  test('should show error state on API failure', async ({ page }) => {
    await page.route('**/api/{resource}', route => 
      route.fulfill({ status: 500 })
    );
    await page.goto('/{route}');
    await expect(page.getByText('Something went wrong')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
  });
});
```

### User Interaction Test

```typescript
test.describe('{Feature} Interactions - {FR_IDs}', () => {
  test('should create new {resource}', async ({ page }) => {
    // Navigate to form
    await page.goto('/{route}');
    await page.getByRole('button', { name: 'Create' }).click();

    // Fill form
    await page.getByLabel('Title').fill('Test Title');
    await page.getByLabel('Description').fill('Test Description');

    // Submit
    await page.getByRole('button', { name: 'Submit' }).click();

    // Verify success
    await expect(page.getByText('Created successfully')).toBeVisible();
  });

  test('should show validation errors', async ({ page }) => {
    await page.goto('/{route}/new');
    
    // Submit empty form
    await page.getByRole('button', { name: 'Submit' }).click();

    // Verify errors
    await expect(page.getByText('Title is required')).toBeVisible();
  });

  test('should delete {resource} with confirmation', async ({ page }) => {
    await page.goto('/{route}');
    
    // Click delete
    await page.getByRole('button', { name: 'Delete' }).first().click();
    
    // Confirm dialog
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByRole('button', { name: 'Confirm' }).click();

    // Verify deleted
    await expect(page.getByText('Deleted successfully')).toBeVisible();
  });
});
```

### Navigation Test

```typescript
test.describe('Navigation - {FR_IDs}', () => {
  test('should navigate to detail page', async ({ page }) => {
    await page.goto('/{route}');
    await page.getByRole('link', { name: 'View Details' }).first().click();
    await expect(page).toHaveURL(/\/{route}\/\d+/);
  });

  test('should go back to list', async ({ page }) => {
    await page.goto('/{route}/1');
    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page).toHaveURL('/{route}');
  });
});
```

### Authentication Test

```typescript
test.describe('Authentication', () => {
  test('should redirect to login when not authenticated', async ({ page }) => {
    await page.goto('/protected-route');
    await expect(page).toHaveURL(/\/login/);
  });

  test('should access protected route when authenticated', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.getByLabel('Email').fill('user@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Login' }).click();

    // Access protected route
    await page.goto('/protected-route');
    await expect(page).toHaveURL('/protected-route');
  });
});
```

## Playwright Configuration

### playwright.config.ts

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Mobile viewport (if responsive)
    {
      name: 'mobile',
      use: { ...devices['iPhone 13'] },
    },
  ],

  // Dev server
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

## Test Run Commands

| Action | Command |
|--------|---------|
| Run all | `npx playwright test` |
| Run specific file | `npx playwright test e2e/alerts.spec.ts` |
| Run headed (visible) | `npx playwright test --headed` |
| Run with UI | `npx playwright test --ui` |
| Debug mode | `npx playwright test --debug` |
| Generate report | `npx playwright show-report` |

## API Mocking Patterns

### Mock API Response

```typescript
test('with mocked API', async ({ page }) => {
  await page.route('**/api/alerts', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 1, message: 'Mock Alert 1' },
        { id: 2, message: 'Mock Alert 2' },
      ]),
    });
  });

  await page.goto('/alerts');
  await expect(page.getByText('Mock Alert 1')).toBeVisible();
});
```

### Mock Error Response

```typescript
test('handles API error', async ({ page }) => {
  await page.route('**/api/alerts', route => {
    route.fulfill({
      status: 500,
      body: JSON.stringify({ error: 'Internal Server Error' }),
    });
  });

  await page.goto('/alerts');
  await expect(page.getByText('Something went wrong')).toBeVisible();
});
```

### Mock Delayed Response

```typescript
test('shows loading state', async ({ page }) => {
  await page.route('**/api/alerts', async route => {
    await new Promise(resolve => setTimeout(resolve, 2000));
    route.fulfill({ json: [] });
  });

  await page.goto('/alerts');
  await expect(page.getByTestId('loading')).toBeVisible();
});
```

## Selector Strategies

| Priority | Strategy | Example |
|----------|----------|---------|
| 1 | Role | `page.getByRole('button', { name: 'Submit' })` |
| 2 | Label | `page.getByLabel('Email')` |
| 3 | Placeholder | `page.getByPlaceholder('Enter email')` |
| 4 | Text | `page.getByText('Welcome')` |
| 5 | Test ID | `page.getByTestId('alert-list')` |
| 6 | CSS (last resort) | `page.locator('.alert-item')` |

## Assertion Patterns

| Assertion | Example |
|-----------|---------|
| Visible | `await expect(locator).toBeVisible()` |
| Hidden | `await expect(locator).toBeHidden()` |
| Text content | `await expect(locator).toHaveText('Expected')` |
| Contains text | `await expect(locator).toContainText('partial')` |
| URL | `await expect(page).toHaveURL('/path')` |
| Title | `await expect(page).toHaveTitle('Page Title')` |
| Count | `await expect(locator).toHaveCount(5)` |
| Attribute | `await expect(locator).toHaveAttribute('disabled')` |

## Visual Testing (Optional)

```typescript
test('visual regression', async ({ page }) => {
  await page.goto('/alerts');
  await expect(page).toHaveScreenshot('alerts-page.png');
});
```

## Accessibility Testing

```typescript
import AxeBuilder from '@axe-core/playwright';

test('should not have accessibility violations', async ({ page }) => {
  await page.goto('/alerts');
  
  const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
  
  expect(accessibilityScanResults.violations).toEqual([]);
});
```
