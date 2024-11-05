import { expect, test } from "@playwright/test";

test("when auto_login is false, admin can CRUD user's and should see just your own flows", async ({
  page,
}) => {
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

  await page.waitForTimeout(1000);

  await page.locator("#is_active").click();

  await page.getByText("Save", { exact: true }).click();

  await page.waitForSelector("text=new user added", { timeout: 30000 });

  expect(await page.getByText(randomName, { exact: true }).isVisible()).toBe(
    true,
  );

  await page.getByTestId("icon-Trash2").last().click();
  await page.getByText("Delete", { exact: true }).last().click();

  await page.waitForSelector("text=user deleted", { timeout: 30000 });

  expect(await page.getByText(randomName, { exact: true }).isVisible()).toBe(
    false,
  );

  await page.getByText("New User", { exact: true }).click();

  await page.getByPlaceholder("Username").last().fill(randomName);
  await page.locator('input[name="password"]').fill(randomPassword);
  await page.locator('input[name="confirmpassword"]').fill(randomPassword);

  await page.waitForTimeout(1000);

  await page.locator("#is_active").click();

  await page.getByText("Save", { exact: true }).click();

  await page.waitForSelector("text=new user added", { timeout: 30000 });

  await page.getByPlaceholder("Username").last().fill(randomName);

  await page.getByTestId("icon-Pencil").last().click();

  await page.getByPlaceholder("Username").last().fill(secondRandomName);

  await page.getByText("Save", { exact: true }).click();

  await page.waitForSelector("text=user edited", { timeout: 30000 });

  await page.waitForTimeout(1000);

  expect(
    await page.getByText(secondRandomName, { exact: true }).isVisible(),
  ).toBe(true);

  //user must see just your own flows
  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();

  await page.getByTestId("flow-configuration-button").click();
  await page.getByText("Settings", { exact: true }).last().click();

  await page.getByPlaceholder("Flow Name").fill(randomFlowName);

  await page.getByText("Save", { exact: true }).click();

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
    state: "visible",
  });

  await page.waitForTimeout(2000);

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.waitForSelector('[data-testid="search-store-input"]:enabled', {
    timeout: 30000,
    state: "visible",
  });

  expect(
    await page.getByText(randomFlowName, { exact: true }).last().isVisible(),
  ).toBe(true);

  await page.getByTestId("user-profile-settings").click();

  await page.getByText("Logout", { exact: true }).click();

  await page.waitForSelector("text=sign in to langflow", { timeout: 30000 });

  await page.getByPlaceholder("Username").fill(secondRandomName);
  await page.getByPlaceholder("Password").fill(randomPassword);
  await page.waitForTimeout(1000);

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

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  await page.getByText("New Flow", { exact: true }).click();

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();

  await page.getByTestId("flow-configuration-button").click();
  await page.getByText("Settings", { exact: true }).last().click();

  await page.getByPlaceholder("Flow Name").fill(secondRandomFlowName);

  await page.getByText("Save", { exact: true }).click();

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.waitForSelector('[data-testid="search-store-input"]:enabled', {
    timeout: 30000,
  });

  await page.waitForTimeout(1000);

  expect(
    await page.getByText(secondRandomFlowName, { exact: true }).isVisible(),
  ).toBe(true);

  expect(
    await page.getByText(randomFlowName, { exact: true }).isVisible(),
  ).toBe(false);

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
  expect(
    await page.getByText(randomFlowName, { exact: true }).isVisible(),
  ).toBe(true);
});
