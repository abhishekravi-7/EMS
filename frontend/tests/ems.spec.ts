import { test, expect } from '@playwright/test';

test.describe('EMS Frontend Application Tests', () => {

  test.beforeEach(async ({ page }) => {
    // Navigate to the app (which will redirect to login if unauthenticated)
    await page.goto('/');
  });

  test('should display the login page correctly', async ({ page }) => {
    await expect(page.locator('h2')).toHaveText('EMS Login');
    await expect(page.locator('input[type="text"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should fail login with incorrect credentials', async ({ page }) => {
    await page.fill('input[type="text"]', 'wrong');
    await page.fill('input[type="password"]', 'wrong');
    await page.click('button[type="submit"]');

    // Check for error message
    await expect(page.locator('text=Invalid username or password')).toBeVisible();
  });

  test('should successfully login and view the dashboard', async ({ page }) => {
    // Perform Login
    await page.fill('input[type="text"]', 'EMS');
    await page.fill('input[type="password"]', 'EMS');
    await page.click('button[type="submit"]');

    // Should redirect to Dashboard which contains "Employee Management System" in the Navbar
    await expect(page.locator('header.navbar')).toContainText('Employee Management System');
    
    // Verify Dashboard Cards are rendered
    await expect(page.locator('text=Active Employees')).toBeVisible();
    await expect(page.locator('text=Total Salary Paid')).toBeVisible();
  });

  test('should navigate to Employees List via sidebar', async ({ page }) => {
    // Perform Login first
    await page.fill('input[type="text"]', 'EMS');
    await page.fill('input[type="password"]', 'EMS');
    await page.click('button[type="submit"]');

    // Click on Employees in the sidebar
    await page.click('.sidebar a[href="/employees"]');
    
    // Verify URL changes
    await expect(page).toHaveURL(/.*\/employees/);
    
    // Verify Employees List header
    await expect(page.locator('h2')).toHaveText('Employees');
  });

  test('should successfully logout', async ({ page }) => {
    // Perform Login first
    await page.fill('input[type="text"]', 'EMS');
    await page.fill('input[type="password"]', 'EMS');
    await page.click('button[type="submit"]');

    // Wait for navbar
    await expect(page.locator('header.navbar')).toBeVisible();

    // Click Logout button
    await page.click('button:has-text("Logout")');

    // Should redirect back to Login
    await expect(page.locator('h2')).toHaveText('EMS Login');
  });

  test('should navigate to Attendance List and view records', async ({ page }) => {
    // Perform Login
    await page.fill('input[type="text"]', 'EMS');
    await page.fill('input[type="password"]', 'EMS');
    await page.click('button[type="submit"]');

    // Click on Attendance in the sidebar
    await page.click('.sidebar a[href="/attendance"]');
    
    // Verify URL changes
    await expect(page).toHaveURL(/.*\/attendance/);
    
    // Verify Attendance Log header
    await expect(page.locator('h2')).toHaveText('Attendance Log');
    
    // Verify the table columns are present
    await expect(page.locator('th').filter({ hasText: 'Employee' })).toBeVisible();
    await expect(page.locator('th').filter({ hasText: 'Date' })).toBeVisible();
    await expect(page.locator('th').filter({ hasText: 'Status' })).toBeVisible();
  });

});

