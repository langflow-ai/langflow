import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "when auto_login is false, admin can CRUD user's and should see just your own flows",
  { tag: ["@release", "@api", "@database"] },
  async ({ page }) => {
    await page.route("**/api/v1/auto_login", (route) => {
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          detail: { auto_login: false },
        }),
      });
    });

    const randomName = Math.random().toString(36).substring(5);
    const randomPassword = Math.random().toString(36).substring(5);
    const secondRandomName = Math.random().toString(36).substring(5);
    const randomFlowName = Math.random().toString(36).substring(5);
    const secondRandomFlowName = Math.random().toString(36).substring(5);

    await page.goto("/");

    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

    await page.getByPlaceholder("Username").fill("langflow");
    await page.getByPlaceholder("Password").fill("langflow");

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

    await page.getByTestId("icon-Trash2").last().click();
    await page.getByText("Delete", { exact: true }).last().click();

    await page.waitForSelector("text=user deleted", { timeout: 30000 });

    await expect(page.getByText(randomName, { exact: true })).toBeVisible({
      timeout: 2000,
      visible: false,
    });

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

    await page.getByPlaceholder("Username").last().fill(randomName);

    await page.getByTestId("icon-Pencil").last().click();

    await page.getByPlaceholder("Username").last().fill(secondRandomName);

    await page.getByText("Save", { exact: true }).click();

    await page.waitForSelector("text=user edited", { timeout: 30000 });

    await expect(page.getByText(secondRandomName, { exact: true })).toBeVisible(
      {
        timeout: 2000,
      },
    );

    //user must see just your own flows
    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

    await awaitBootstrapTest(page, { skipGoto: true });

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("flow-configuration-button").click();
    await page.getByText("Flow Settings", { exact: true }).last().click();

    await page.getByPlaceholder("Flow Name").fill(randomFlowName);

    await page.getByText("Save", { exact: true }).click();

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
      state: "visible",
    });

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 1500,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="search-store-input"]:enabled', {
      timeout: 30000,
      state: "visible",
    });

    await expect(page.getByText(randomFlowName, { exact: true })).toBeVisible({
      timeout: 2000,
    });

    await page.waitForSelector("[data-testid='user-profile-settings']", {
      timeout: 1500,
    });

    await page.getByTestId("user-profile-settings").click();

    await page.getByText("Logout", { exact: true }).click();

    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

    await page.getByPlaceholder("Username").fill(secondRandomName);
    await page.getByPlaceholder("Password").fill(randomPassword);

    await page.waitForSelector("text=Sign in", {
      timeout: 1500,
    });

    await page.getByRole("button", { name: "Sign In" }).click();

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

    expect(
      (
        await page.waitForSelector(
          "text=Begin with a template, or start from scratch.",
          {
            timeout: 30000,
          },
        )
      ).isVisible(),
    );

    await awaitBootstrapTest(page, { skipGoto: true });

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("flow-configuration-button").click();
    await page.getByText("Flow Settings", { exact: true }).last().click();

    await page.getByPlaceholder("Flow Name").fill(secondRandomFlowName);

    await page.getByText("Save", { exact: true }).click();

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="search-store-input"]:enabled', {
      timeout: 30000,
    });

    await expect(
      page.getByText(secondRandomFlowName, { exact: true }),
    ).toBeVisible({
      timeout: 2000,
    });

    await expect(page.getByText(randomFlowName, { exact: true })).toBeVisible({
      timeout: 2000,
      visible: false,
    });

    await page.getByTestId("user-profile-settings").click();

    await page.getByText("Logout", { exact: true }).click();

    await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

    await page.getByPlaceholder("Username").fill("langflow");
    await page.getByPlaceholder("Password").fill("langflow");

    await page.getByRole("button", { name: "Sign In" }).click();

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[data-testid="search-store-input"]:enabled', {
      timeout: 30000,
    });

    expect(
      await page.getByText(secondRandomFlowName, { exact: true }).isVisible(),
    ).toBe(false);

    await expect(page.getByText(randomFlowName, { exact: true })).toBeVisible({
      timeout: 2000,
    });
  },
);
