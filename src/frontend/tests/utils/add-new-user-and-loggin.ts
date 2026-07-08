import { type Page } from "@playwright/test";
import { expect } from "../fixtures";
import { TEXTS } from "../utils/constants/texts";
import { waitForNewProjectButton } from "./flow/new-project-flow";
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

  await page.waitForSelector(`text=${TEXTS.authSignInHeader}`, {
    timeout: 30000,
  });

  await page
    .getByPlaceholder(TEXTS.placeholderUsername)
    .fill(TEXTS.authDefaultCredential);
  await page
    .getByPlaceholder(TEXTS.placeholderPassword)
    .fill(TEXTS.authDefaultPassword);

  await page.evaluate(() => {
    sessionStorage.removeItem("testMockAutoLogin");
  });

  await page.getByRole("button", { name: TEXTS.signIn }).click();

  // Wait for any loading text to disappear before checking the homepage:
  // mainpage_title only renders after the homepage data finishes loading,
  // and on slower runners (Windows CI) the Loading state can outlast a
  // 30s mainpage_title wait.
  await page.waitForSelector('text="Loading"', {
    state: "hidden",
    timeout: 60000,
  });

  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await waitForNewProjectButton(page);

  await page.getByTestId("user-profile-settings").click();

  await page.getByText("Admin Page", { exact: true }).click();

  //CRUD an user
  await page.getByText("New User", { exact: true }).click();

  await page
    .getByPlaceholder(TEXTS.placeholderUsername)
    .last()
    .fill(randomName);
  await page.locator('input[name="password"]').fill(randomPassword);
  await page.locator('input[name="confirmpassword"]').fill(randomPassword);

  await page.waitForSelector("#is_active", {
    timeout: 1500,
  });

  await page.locator("#is_active").click();

  await page.getByText(TEXTS.save, { exact: true }).click();

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

  await page.getByText(TEXTS.logout, { exact: true }).click();

  await page.waitForSelector(`text=${TEXTS.authSignInHeader}`, {
    timeout: 30000,
  });

  await page.getByPlaceholder(TEXTS.placeholderUsername).fill(randomName);
  await page.getByPlaceholder(TEXTS.placeholderPassword).fill(randomPassword);

  await page.waitForSelector("text=Sign in", {
    timeout: 1500,
  });

  await page.getByRole("button", { name: TEXTS.signIn }).click();

  await page.evaluate(() => {
    sessionStorage.removeItem("testMockAutoLogin");
  });

  // Wait for any loading text to disappear
  await page.waitForSelector('text="Loading"', {
    state: "hidden",
    timeout: 30000,
  });
};
