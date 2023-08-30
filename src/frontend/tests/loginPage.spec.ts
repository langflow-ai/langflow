import { test, expect } from '@playwright/test';

test('test', async ({ page }) => {
  await page.goto('http://localhost:3000/');
  await page.goto('http://localhost:3000/login');
  await expect(page.getByText('Sign in to Langflow')).toBeVisible();
});