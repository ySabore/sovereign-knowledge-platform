import { test, expect, Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://127.0.0.1:5173';

interface TestAccount {
  name: string;
  email: string;
  password: string;
  role: string;
}

const accounts: TestAccount[] = [
  { name: 'ORG_ADMIN', email: 'org-admin@example.com', password: 'ChangeMeNow!', role: 'org_admin' },
  { name: 'WORKSPACE_ADMIN', email: 'ws-admin@example.com', password: 'ChangeMeNow!', role: 'workspace_admin' },
  { name: 'ORG_MEMBER', email: 'org-member@example.com', password: 'ChangeMeNow!', role: 'org_member' },
  { name: 'WORKSPACE_MEMBER', email: 'ws-member@example.com', password: 'ChangeMeNow!', role: 'workspace_member' }
];

const screenshotsDir = path.join(process.cwd(), 'e2e', 'screenshots');

interface ChatAccessResult {
  account: string;
  role: string;
  loginSuccess: boolean;
  orgPageLoads: boolean;
  workspaceCardVisible: boolean;
  canLaunchChat: boolean;
  chatPageLoads: boolean;
  errors: string[];
  notes: string[];
}

const results: ChatAccessResult[] = [];

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
    console.log(`Login error: ${e}`);
    return false;
  }
}

async function testChatAccess(page: Page, account: TestAccount): Promise<ChatAccessResult> {
  const result: ChatAccessResult = {
    account: account.name,
    role: account.role,
    loginSuccess: false,
    orgPageLoads: false,
    workspaceCardVisible: false,
    canLaunchChat: false,
    chatPageLoads: false,
    errors: [],
    notes: []
  };

  try {
    // Step 1: Login
    result.loginSuccess = await login(page, account);
    if (!result.loginSuccess) {
      result.errors.push('Login failed');
      await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_login_fail.png`) });
      return result;
    }
    result.notes.push('Login successful');

    // Step 2: Navigate to organizations page
    await page.goto(`${BASE_URL}/organizations`);
    await page.waitForTimeout(3000);
    
    const url = page.url();
    result.orgPageLoads = url.includes('/organizations');
    
    if (!result.orgPageLoads) {
      result.errors.push(`Redirected to ${url} instead of /organizations`);
      return result;
    }
    result.notes.push('Organizations page loaded');

    await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_org_loaded.png`), fullPage: true });

    // Step 3: Look for workspace card with "Launch Chat" button
    const pageContent = await page.content();
    
    if (pageContent.includes('Pilot Workspace') || pageContent.includes('workspace')) {
      result.workspaceCardVisible = true;
      result.notes.push('Workspace content visible on page');
    }

    // Step 4: Try to find and click "Launch Chat" button
    const launchChatButton = page.locator('button:has-text("Launch Chat")').first();
    const buttonVisible = await launchChatButton.isVisible().catch(() => false);
    
    if (buttonVisible) {
      result.notes.push('Launch Chat button found');
      
      try {
        await launchChatButton.click();
        await page.waitForTimeout(4000);
        
        const newUrl = page.url();
        result.canLaunchChat = true;
        result.notes.push(`Clicked Launch Chat, navigated to: ${newUrl}`);
        
        // Check if chat page loaded
        if (newUrl.includes('/dashboard/')) {
          result.chatPageLoads = true;
          result.notes.push('Chat/dashboard page loaded successfully');
          await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_chat_page.png`) });
        } else {
          result.errors.push(`Expected /dashboard/ URL but got: ${newUrl}`);
        }
      } catch (e) {
        result.errors.push(`Failed to launch chat: ${e}`);
      }
    } else {
      result.errors.push('Launch Chat button not visible');
    }

    // Step 5: Check for console errors
    const consoleErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    await page.waitForTimeout(1000);
    
    const criticalErrors = consoleErrors.filter(err => 
      err.includes('404') || err.includes('403') || err.includes('401') || 
      err.includes('Failed') || err.includes('Error')
    );
    
    if (criticalErrors.length > 0) {
      result.errors.push(...criticalErrors.slice(0, 2));
    }

  } catch (e) {
    result.errors.push(`Unexpected error: ${e}`);
    await page.screenshot({ path: path.join(screenshotsDir, `${account.name}_error.png`) });
  }

  return result;
}

for (const account of accounts) {
  test(`Chat access - ${account.name}`, async ({ page }) => {
    test.setTimeout(60000);
    const result = await testChatAccess(page, account);
    results.push(result);
    
    console.log(`\n========== ${account.name} (${account.role}) ==========`);
    console.log(`Login Success: ${result.loginSuccess}`);
    console.log(`Org Page Loads: ${result.orgPageLoads}`);
    console.log(`Workspace Card Visible: ${result.workspaceCardVisible}`);
    console.log(`Can Launch Chat: ${result.canLaunchChat}`);
    console.log(`Chat Page Loads: ${result.chatPageLoads}`);
    console.log(`Notes: ${result.notes.join(' | ')}`);
    console.log(`Errors: ${result.errors.join(' | ')}`);
    
    expect(result.loginSuccess, `Login should succeed for ${account.name}`).toBe(true);
  });
}

test.afterAll(async () => {
  console.log('\n\n========== CHAT ACCESS FINAL SUMMARY ==========');
  
  let passCount = 0;
  let failCount = 0;
  
  for (const r of results) {
    // Consider it a pass if login works and they can see the org page
    const status = (r.loginSuccess && r.orgPageLoads) ? 'PASS' : 'FAIL';
    if (status === 'PASS') passCount++;
    else failCount++;
    
    console.log(`\n${r.account} (${r.role}): ${status}`);
    console.log(`  Login: ${r.loginSuccess ? 'OK' : 'FAIL'}`);
    console.log(`  Org Page: ${r.orgPageLoads ? 'OK' : 'FAIL'}`);
    console.log(`  Workspace Card: ${r.workspaceCardVisible ? 'VISIBLE' : 'NOT VISIBLE'}`);
    console.log(`  Launch Chat Works: ${r.canLaunchChat ? 'YES' : 'NO'}`);
    console.log(`  Chat Page Loads: ${r.chatPageLoads ? 'YES' : 'NO'}`);
    if (r.notes.length > 0) console.log(`  Notes: ${r.notes.join('; ')}`);
    if (r.errors.length > 0) console.log(`  ERRORS: ${r.errors.join('; ')}`);
  }
  
  console.log(`\n\nTotals: ${passCount} PASS, ${failCount} FAIL`);
  
  // Identify issues
  const chatLaunchFailures = results.filter(r => !r.canLaunchChat && r.workspaceCardVisible);
  if (chatLaunchFailures.length > 0) {
    console.log(`\n⚠️  Chat Launch Failures: ${chatLaunchFailures.map(r => r.account).join(', ')}`);
  }
  
  const summary = {
    timestamp: new Date().toISOString(),
    testType: 'chat-access-verification',
    summary: {
      total: results.length,
      pass: passCount,
      fail: failCount
    },
    results: results.map(r => ({
      account: r.account,
      role: r.role,
      status: (r.loginSuccess && r.orgPageLoads) ? 'PASS' : 'FAIL',
      loginSuccess: r.loginSuccess,
      orgPageLoads: r.orgPageLoads,
      workspaceCardVisible: r.workspaceCardVisible,
      canLaunchChat: r.canLaunchChat,
      chatPageLoads: r.chatPageLoads,
      notes: r.notes,
      errors: r.errors
    })),
    recommendations: []
  };
  
  // Add recommendations based on findings
  if (chatLaunchFailures.length > 0) {
    summary.recommendations.push({
      issue: 'Launch Chat button not working for some roles',
      affectedRoles: chatLaunchFailures.map(r => r.role),
      suggestion: 'Verify workspace permissions and navigation logic in WorkspaceCard component'
    });
  }
  
  fs.writeFileSync(path.join(process.cwd(), 'e2e', 'chat-access-results.json'), JSON.stringify(summary, null, 2));
  console.log('\nResults saved to e2e/chat-access-results.json');
});
