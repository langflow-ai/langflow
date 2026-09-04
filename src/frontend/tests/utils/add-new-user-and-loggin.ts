import { expect } from "../fixtures";
import { createActiveUserViaApi } from "./auth/manage-users-via-api";
import { TEXTS } from "./constants/texts";
import { waitForNewProjectButton } from "./flow/new-project-flow";
import type { LangflowPage } from "./types";

export const addNewUserAndLogin = async (page: LangflowPage) => {
  await page.route("**/api/v1/auto_login", (route) => {
    route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({
        detail: {
          message: "Auto login is disabled.",
          auto_login: false,
        },
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

  await expect(page.getByRole("button", { name: TEXTS.signIn })).toBeVisible({
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

  // OSS no longer ships the Admin Page UI; create the user through the
  // authenticated superuser API instead.
  await createActiveUserViaApi(page, {
    username: randomName,
    password: randomPassword,
  });

  await page.waitForSelector("[data-testid='user-profile-settings']", {
    timeout: 1500,
  });

  await page.getByTestId("user-profile-settings").click();

  await page.evaluate(() => {
    sessionStorage.setItem("testMockAutoLogin", "true");
  });

  await page.getByText(TEXTS.logout, { exact: true }).click();

  await expect(page.getByRole("button", { name: TEXTS.signIn })).toBeVisible({
    timeout: 30000,
  });

  await page.getByPlaceholder(TEXTS.placeholderUsername).fill(randomName);
  await page.getByPlaceholder(TEXTS.placeholderPassword).fill(randomPassword);

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
