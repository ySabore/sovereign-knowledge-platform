import { test, expect, Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://127.0.0.1:5173';

interface TestAccount {
  name: string;
  email: string;
  password: string;
}

const accounts: TestAccount[] = [
  { name: 'ORG_ADMIN', email: 'org-admin@example.com', password: 'ChangeMeNow!' },
];

const screenshotsDir = path.join(process.cwd(), 'e2e', 'screenshots');

interface AdminRouteResult {
  route: string;
  loadsWithoutError: boolean;
  showsContent: boolean;
  errors: string[];
  notes: string[];
}

const results: AdminRouteResult[] = [];

async function login(page: Page, account: TestAccount): Promise<boolean> {
  try {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector('.sk-input', { timeout: 10000 });
    
    await page.locator('input[type="email"].sk-input').fill(account.email);
    await page.locator('input[type="password"].sk-input').fill(account.password);
    await page.locator('button.sk-btn[type="submit"]').click();
    
    await page.waitForTimeout(3000);
    const url = page.url();
    return url.includes('/organizations') || url.includes('/home') || url.includes('/dashboard');
  } catch (e) {
    return false;
  }
}

const adminRoutes = [
  '/admin',
  '/admin/documents',
  '/admin/team',
  '/admin/billing',
  '/admin/audit',
  '/admin/settings',
  '/admin/connectors',
];

for (const route of adminRoutes) {
  test(`Admin route - ${route}`, async ({ page }) => {
    test.setTimeout(30000);
    
    const result: AdminRouteResult = {
      route,
      loadsWithoutError: false,
      showsContent: false,
      errors: [],
      notes: []
    };

    try {
      // Login first
      const loggedIn = await login(page, { name: 'ORG_ADMIN', email: 'org-admin@example.com', password: 'ChangeMeNow!' });
      if (!loggedIn) {
        result.errors.push('Login failed');
        results.push(result);
        return;
      }

      // Navigate to admin route
      await page.goto(`${BASE_URL}${route}`);
      await page.waitForTimeout(3000);
      
      const url = page.url();
      result.notes.push(`Navigated to: ${url}`);
      
      // Check if page loaded without crashing
      const pageContent = await page.content();
      result.loadsWithoutError = !pageContent.includes('404') && !pageContent.includes('Error');
      
      // Check for visible content
      result.showsContent = pageContent.length > 1000;
      
      // Check for console errors
      const consoleErrors: string[] = [];
      page.on('console', msg => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text());
        }
      });
      await page.waitForTimeout(1000);
      
      const apiErrors = consoleErrors.filter(err => 
        err.includes('404') || err.includes('/admin/') || err.includes('Failed')
      );
      
      if (apiErrors.length > 0) {
        result.errors.push(...apiErrors.slice(0, 2));
      }
      
      await page.screenshot({ path: path.join(screenshotsDir, `admin_${route.replace(/\//g, '_')}.png`) });
      
    } catch (e) {
      result.errors.push(`Unexpected error: ${e}`);
    }

    results.push(result);
    
    console.log(`\n========== ${route} ==========`);
    console.log(`Loads Without Error: ${result.loadsWithoutError}`);
    console.log(`Shows Content: ${result.showsContent}`);
    console.log(`Notes: ${result.notes.join(' | ')}`);
    console.log(`Errors: ${result.errors.join(' | ')}`);
  });
}

test.afterAll(async () => {
  console.log('\n\n========== ADMIN ROUTES SUMMARY ==========');
  
  for (const r of results) {
    const status = r.loadsWithoutError ? 'PASS' : 'FAIL';
    console.log(`\n${r.route}: ${status}`);
    console.log(`  Loads Without Error: ${r.loadsWithoutError ? 'YES' : 'NO'}`);
    console.log(`  Shows Content: ${r.showsContent ? 'YES' : 'NO'}`);
    if (r.notes.length > 0) console.log(`  Notes: ${r.notes.join('; ')}`);
    if (r.errors.length > 0) console.log(`  ERRORS: ${r.errors.join('; ')}`);
  }
  
  const summary = {
    timestamp: new Date().toISOString(),
    testType: 'admin-routes-verification',
    results: results.map(r => ({
      route: r.route,
      status: r.loadsWithoutError ? 'PASS' : 'FAIL',
      loadsWithoutError: r.loadsWithoutError,
      showsContent: r.showsContent,
      notes: r.notes,
      errors: r.errors
    }))
  };
  
  fs.writeFileSync(path.join(process.cwd(), 'e2e', 'admin-routes-results.json'), JSON.stringify(summary, null, 2));
  console.log('\nResults saved to e2e/admin-routes-results.json');
});