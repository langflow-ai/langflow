import { expect, Page } from "@playwright/test";

export const addNewUserAndLogin = async (page: Page) => {
  await page.route("**/api/v1/auto_login", (route) => {
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        detail: { auto_login: false },
      }),
    });
  });

  await page.addInitScript(() => {
    window.process = window.process || {};

    const newEnv = { ...window.process.env, LANGFLOW_AUTO_LOGIN: "false" };

    Object.defineProperty(window.process, "env", {
      value: newEnv,
      writable: true,
      configurable: true,
    });

    sessionStorage.setItem("testMockAutoLogin", "true");
  });

  const randomName = Math.random().toString(36).substring(5);
  const randomPassword = Math.random().toString(36).substring(5);

  await page.goto("/");

  await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

  await page.getByPlaceholder("Username").fill("langflow");
  await page.getByPlaceholder("Password").fill("langflow");

  await page.evaluate(() => {
    sessionStorage.removeItem("testMockAutoLogin");
  });

  await page.getByRole("button", { name: "Sign In" }).click();

  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  await page.getByTestId("user-profile-settings").click();

  await page.getByText("Admin Page", { exact: true }).click();

  //CRUD an user
  await page.getByText("New User", { exact: true }).click();

  await page.getByPlaceholder("Username").last().fill(randomName);
  await page.locator('input[name="password"]').fill(randomPassword);
  await page.locator('input[name="confirmpassword"]').fill(randomPassword);

  await page.waitForSelector("#is_active", {
    timeout: 1500,
  });

  await page.locator("#is_active").click();

  await page.getByText("Save", { exact: true }).click();

  await page.waitForSelector("text=new user added", { timeout: 30000 });

  await expect(page.getByText(randomName, { exact: true })).toBeVisible({
    timeout: 2000,
  });

  await page.waitForSelector("[data-testid='user-profile-settings']", {
    timeout: 1500,
  });

  await page.getByTestId("user-profile-settings").click();

  await page.evaluate(() => {
    sessionStorage.setItem("testMockAutoLogin", "true");
  });

  await page.getByText("Logout", { exact: true }).click();

  await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

  await page.getByPlaceholder("Username").fill(randomName);
  await page.getByPlaceholder("Password").fill(randomPassword);

  await page.waitForSelector("text=Sign in", {
    timeout: 1500,
  });

  await page.getByRole("button", { name: "Sign In" }).click();

  await page.evaluate(() => {
    sessionStorage.removeItem("testMockAutoLogin");
  });
};
