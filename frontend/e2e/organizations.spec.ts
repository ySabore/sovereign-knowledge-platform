import { test, expect, Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://127.0.0.1:5173';
const API_URL = 'http://127.0.0.1:8000';

interface TestAccount {
  name: string;
  email: string;
  password: string;
  expectedRole: string;
}

const accounts: TestAccount[] = [
  {
    name: 'ORG_ADMIN',
    email: 'org-admin@example.com',
    password: 'ChangeMeNow!',
    expectedRole: 'org_admin'
  },
  {
    name: 'WORKSPACE_ADMIN',
    email: 'ws-admin@example.com',
    password: 'ChangeMeNow!',
    expectedRole: 'workspace_admin'
  },
  {
    name: 'ORG_MEMBER',
    email: 'org-member@example.com',
    password: 'ChangeMeNow!',
    expectedRole: 'org_member'
  },
  {
    name: 'WORKSPACE_MEMBER',
    email: 'ws-member@example.com',
    password: 'ChangeMeNow!',
    expectedRole: 'workspace_member'
  }
];

interface TestResult {
  account: string;
  loginSuccess: boolean;
  orgPageLoad: boolean;
  orgListVisible: boolean;
  workspaceListVisible: boolean;
  canEnterWorkspace: boolean;
  errors: string[];
  notes: string[];
  screenshots: string[];
}

const results: TestResult[] = [];

// Create screenshots directory
const screenshotsDir = path.join(process.cwd(), 'e2e', 'screenshots');
if (!fs.existsSync(screenshotsDir)) {
  fs.mkdirSync(screenshotsDir, { recursive: true });
}

async function login(page: Page, account: TestAccount): Promise<boolean> {
  try {
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector('.sk-input', { timeout: 10000 });
    
    // Check if already logged in
    const currentUrl = page.url();
    if (currentUrl.includes('/organizations') || currentUrl.includes('/home')) {
      return true;
    }
    
    // Fill login form - use class selectors based on actual code
    const emailInput = page.locator('input[type="email"].sk-input');
    const passwordInput = page.locator('input[type="password"].sk-input');
    
    await emailInput.fill(account.email);
    await passwordInput.fill(account.password);
    
    // Click login button
    await page.locator('button.sk-btn[type="submit"]').click();
    
    // Wait for navigation - check multiple possible destinations
    await page.waitForTimeout(3000);
    
    const url = page.url();
    return url.includes('/organizations') || url.includes('/home') || url.includes('/dashboard');
  } catch (e) {
    console.log(`Login error for ${account.name}: ${e}`);
    return false;
  }
}

async function testOrganizationsPage(page: Page, account: TestAccount): Promise<TestResult> {
  const result: TestResult = {
    account: account.name,
    loginSuccess: false,
    orgPageLoad: false,
    orgListVisible: false,
    workspaceListVisible: false,
    canEnterWorkspace: false,
    errors: [],
    notes: [],
    screenshots: []
  };

  try {
    // Step 1: Login
    result.loginSuccess = await login(page, account);
    if (!result.loginSuccess) {
      result.errors.push('Login failed or redirected unexpectedly');
      await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_login_fail.png`) });
      result.screenshots.push(`${account.name}_login_fail.png`);
      return result;
    }
    result.notes.push('Login successful');

    // Step 2: Navigate to /organizations
    await page.goto(`${BASE_URL}/organizations`);
    await page.waitForTimeout(3000);
    
    const url = page.url();
    result.orgPageLoad = url.includes('/organizations');
    
    if (!result.orgPageLoad) {
      result.errors.push(`Redirected away from /organizations to ${url}`);
      await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_org_redirect.png`) });
      result.screenshots.push(`${account.name}_org_redirect.png`);
      return result;
    }
    result.notes.push('Organizations page loaded');

    // Take screenshot of org page
    await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_org_page.png`), fullPage: true });
    result.screenshots.push(`${account.name}_org_page.png`);

    // Step 3: Check for org list visibility - look for "Organizations" heading or org names
    const pageContent = await page.content();
    
    if (pageContent.includes('Sterling & Vale LLP') || pageContent.includes('Organizations')) {
      result.orgListVisible = true;
      result.notes.push('Organization list/content visible');
    } else {
      result.errors.push('Organization list not visible');
    }

    // Step 4: Check for workspace list visibility
    if (pageContent.includes('Pilot Workspace') || pageContent.includes('Workspaces')) {
      result.workspaceListVisible = true;
      result.notes.push('Workspace list/content visible');
    } else {
      result.errors.push('Workspace list not visible');
    }

    // Step 5: Check for team/member management surfaces
    const teamManagementIndicators = ['Members', 'Team', 'Invite', 'Add Member'];
    const visibleTeamFeatures = teamManagementIndicators.filter(indicator => 
      pageContent.includes(indicator)
    );
    
    if (visibleTeamFeatures.length > 0) {
      result.notes.push(`Team management features visible: ${visibleTeamFeatures.join(', ')}`);
    }

    // Step 6: Check for admin-only panels that might break
    const adminIndicators = ['Documents', 'Metrics', 'Admin Dashboard'];
    const visibleAdminFeatures = adminIndicators.filter(indicator => 
      pageContent.includes(indicator)
    );
    
    if (visibleAdminFeatures.length > 0) {
      result.notes.push(`Admin features visible: ${visibleAdminFeatures.join(', ')}`);
    }

    // Step 7: Try to find and click workspace entry
    const workspaceLinks = await page.locator('a[href*="/dashboard/"], a[href*="/workspaces/"], button:has-text("Open"), button:has-text("Enter")').all();
    
    if (workspaceLinks.length > 0) {
      try {
        await workspaceLinks[0].click();
        await page.waitForTimeout(2000);
        
        const newUrl = page.url();
        if (newUrl.includes('/dashboard/') || newUrl.includes('/workspaces/')) {
          result.canEnterWorkspace = true;
          result.notes.push(`Successfully navigated to workspace: ${newUrl}`);
          await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_workspace.png`) });
          result.screenshots.push(`${account.name}_workspace.png`);
        }
      } catch (e) {
        result.errors.push(`Failed to enter workspace: ${e}`);
      }
    }

    // Step 8: Check for console errors related to /admin endpoints
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    await page.waitForTimeout(1000);
    
    // Filter for critical errors related to missing admin endpoints
    const adminErrors = consoleErrors.filter(err => 
      err.includes('/admin/') && (err.includes('404') || err.includes('Failed'))
    );
    
    if (adminErrors.length > 0) {
      result.errors.push(...adminErrors.slice(0, 2));
    }

  } catch (e) {
    result.errors.push(`Unexpected error: ${e}`);
    await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_error.png`) });
    result.screenshots.push(`${account.name}_error.png`);
  }

  return result;
}

for (const account of accounts) {
  test(`Organizations page - ${account.name}`, async ({ page }) => {
    test.setTimeout(60000);
    const result = await testOrganizationsPage(page, account);
    results.push(result);
    
    // Output detailed results to console
    console.log(`\n========== ${account.name} ==========`);
    console.log(`Login Success: ${result.loginSuccess}`);
    console.log(`Org Page Load: ${result.orgPageLoad}`);
    console.log(`Org List Visible: ${result.orgListVisible}`);
    console.log(`Workspace List Visible: ${result.workspaceListVisible}`);
    console.log(`Can Enter Workspace: ${result.canEnterWorkspace}`);
    console.log(`Notes: ${result.notes.join(' | ')}`);
    console.log(`Errors: ${result.errors.join(' | ')}`);
    console.log(`Screenshots: ${result.screenshots.join(', ')}`);
    
    // Assertions - be lenient for workspace_member who may have limited access
    expect(result.loginSuccess, `Login should succeed for ${account.name}`).toBe(true);
  });
}

test.afterAll(async () => {
  console.log('\n\n========== FINAL SUMMARY ==========');
  for (const r of results) {
    const status = r.errors.length === 0 && r.orgPageLoad ? 'PASS' : 'FAIL';
    console.log(`\n${r.account}: ${status}`);
    console.log(`  Login: ${r.loginSuccess ? 'OK' : 'FAIL'}`);
    console.log(`  Org Page: ${r.orgPageLoad ? 'OK' : 'FAIL'}`);
    console.log(`  Org List: ${r.orgListVisible ? 'VISIBLE' : 'NOT VISIBLE'}`);
    console.log(`  Workspace List: ${r.workspaceListVisible ? 'VISIBLE' : 'NOT VISIBLE'}`);
    console.log(`  Can Enter Workspace: ${r.canEnterWorkspace ? 'YES' : 'NO'}`);
    if (r.notes.length > 0) console.log(`  Notes: ${r.notes.join('; ')}`);
    if (r.errors.length > 0) console.log(`  ERRORS: ${r.errors.join('; ')}`);
  }
  
  // Write summary to file
  const summary = {
    timestamp: new Date().toISOString(),
    results: results.map(r => ({
      account: r.account,
      status: r.errors.length === 0 && r.orgPageLoad ? 'PASS' : 'FAIL',
      loginSuccess: r.loginSuccess,
      orgPageLoad: r.orgPageLoad,
      orgListVisible: r.orgListVisible,
      workspaceListVisible: r.workspaceListVisible,
      canEnterWorkspace: r.canEnterWorkspace,
      notes: r.notes,
      errors: r.errors
    }))
  };
  
  fs.writeFileSync(path.join(process.cwd(), 'e2e', 'test-results.json'), JSON.stringify(summary, null, 2));
  console.log('\nResults saved to e2e/test-results.json');
});
