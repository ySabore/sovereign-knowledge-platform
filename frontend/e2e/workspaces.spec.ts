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
  { name: 'WORKSPACE_ADMIN', email: 'ws-admin@example.com', password: 'ChangeMeNow!' },
  { name: 'ORG_MEMBER', email: 'org-member@example.com', password: 'ChangeMeNow!' },
  { name: 'WORKSPACE_MEMBER', email: 'ws-member@example.com', password: 'ChangeMeNow!' }
];

const screenshotsDir = path.join(process.cwd(), 'e2e', 'screenshots');

interface WorkspaceTestResult {
  account: string;
  canAccessWorkspacesNav: boolean;
  workspacesListVisible: boolean;
  canOpenWorkspace: boolean;
  chatInterfaceLoads: boolean;
  errors: string[];
  notes: string[];
}

const results: WorkspaceTestResult[] = [];

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

async function testWorkspaceAccess(page: Page, account: TestAccount): Promise<WorkspaceTestResult> {
  const result: WorkspaceTestResult = {
    account: account.name,
    canAccessWorkspacesNav: false,
    workspacesListVisible: false,
    canOpenWorkspace: false,
    chatInterfaceLoads: false,
    errors: [],
    notes: []
  };

  try {
    // Login
    const loggedIn = await login(page, account);
    if (!loggedIn) {
      result.errors.push('Login failed');
      return result;
    }

    // Navigate to /organizations first
    await page.goto(`${BASE_URL}/organizations`);
    await page.waitForTimeout(2000);

    // Try to click on Workspaces in left nav
    const workspacesNav = page.locator('text=Workspaces').first();
    const navVisible = await workspacesNav.isVisible().catch(() => false);
    
    if (navVisible) {
      result.canAccessWorkspacesNav = true;
      result.notes.push('Workspaces nav item visible');
      
      try {
        await workspacesNav.click();
        await page.waitForTimeout(2000);
        result.notes.push('Clicked Workspaces nav');
      } catch (e) {
        result.errors.push(`Failed to click Workspaces nav: ${e}`);
      }
    } else {
      result.errors.push('Workspaces nav item not visible');
    }

    // Check for workspaces list
    const pageContent = await page.content();
    if (pageContent.includes('Pilot Workspace') || pageContent.includes('workspaces')) {
      result.workspacesListVisible = true;
      result.notes.push('Workspaces list/content visible');
    }

    // Try to find and click on a workspace card/link
    // Look for the workspace card or "Open" button
    const workspaceSelectors = [
      'text=Pilot Workspace',
      '.workspace-card',
      'button:has-text("Open")',
      'a[href*="/dashboard/"]',
      '[data-testid="workspace-card"]'
    ];

    for (const selector of workspaceSelectors) {
      const element = page.locator(selector).first();
      const visible = await element.isVisible().catch(() => false);
      
      if (visible) {
        try {
          await element.click();
          await page.waitForTimeout(3000);
          
          const url = page.url();
          if (url.includes('/dashboard/') || url.includes('/chat')) {
            result.canOpenWorkspace = true;
            result.notes.push(`Opened workspace at: ${url}`);
            
            // Check if chat interface loads
            await page.waitForTimeout(2000);
            const chatContent = await page.content();
            
            if (chatContent.includes('chat') || chatContent.includes('message') || chatContent.includes('input')) {
              result.chatInterfaceLoads = true;
              result.notes.push('Chat interface appears to load');
            }
            
            await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_chat.png`) });
          }
          break;
        } catch (e) {
          result.errors.push(`Failed to open workspace: ${e}`);
        }
      }
    }

    // Check for API errors in console
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    await page.waitForTimeout(1000);
    
    const apiErrors = consoleErrors.filter(err => 
      err.includes('404') || err.includes('403') || err.includes('401') || err.includes('Failed to fetch')
    );
    
    if (apiErrors.length > 0) {
      result.errors.push(...apiErrors.slice(0, 3));
    }

  } catch (e) {
    result.errors.push(`Unexpected error: ${e}`);
  }

  return result;
}

for (const account of accounts) {
  test(`Workspace access - ${account.name}`, async ({ page }) => {
    test.setTimeout(60000);
    const result = await testWorkspaceAccess(page, account);
    results.push(result);
    
    console.log(`\n========== ${account.name} ==========`);
    console.log(`Can Access Workspaces Nav: ${result.canAccessWorkspacesNav}`);
    console.log(`Workspaces List Visible: ${result.workspacesListVisible}`);
    console.log(`Can Open Workspace: ${result.canOpenWorkspace}`);
    console.log(`Chat Interface Loads: ${result.chatInterfaceLoads}`);
    console.log(`Notes: ${result.notes.join(' | ')}`);
    console.log(`Errors: ${result.errors.join(' | ')}`);
    
    expect(result.canAccessWorkspacesNav, `Should see Workspaces nav for ${account.name}`).toBe(true);
  });
}

test.afterAll(async () => {
  console.log('\n\n========== WORKSPACE ACCESS SUMMARY ==========');
  for (const r of results) {
    const status = r.canOpenWorkspace ? 'PASS' : 'PARTIAL';
    console.log(`\n${r.account}: ${status}`);
    console.log(`  Nav Access: ${r.canAccessWorkspacesNav ? 'YES' : 'NO'}`);
    console.log(`  List Visible: ${r.workspacesListVisible ? 'YES' : 'NO'}`);
    console.log(`  Can Open: ${r.canOpenWorkspace ? 'YES' : 'NO'}`);
    console.log(`  Chat Loads: ${r.chatInterfaceLoads ? 'YES' : 'NO'}`);
    if (r.notes.length > 0) console.log(`  Notes: ${r.notes.join('; ')}`);
    if (r.errors.length > 0) console.log(`  ERRORS: ${r.errors.join('; ')}`);
  }
  
  const summary = {
    timestamp: new Date().toISOString(),
    testType: 'workspace-access',
    results: results.map(r => ({
      account: r.account,
      status: r.canOpenWorkspace ? 'PASS' : 'PARTIAL',
      canAccessWorkspacesNav: r.canAccessWorkspacesNav,
      workspacesListVisible: r.workspacesListVisible,
      canOpenWorkspace: r.canOpenWorkspace,
      chatInterfaceLoads: r.chatInterfaceLoads,
      notes: r.notes,
      errors: r.errors
    }))
  };
  
  fs.writeFileSync(path.join(process.cwd(), 'e2e', 'workspace-test-results.json'), JSON.stringify(summary, null, 2));
});
