import { test } from "@playwright/test";

test("user should be able to download a flow or a component", async ({
  page,
}) => {
  await page.goto("/");

  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

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
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  await page.getByText("Chat Input", { exact: true }).click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.waitForTimeout(1000);

  if (await page.getByTestId("replace-button").isVisible()) {
    await page.getByTestId("replace-button").click();
  }

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  const exitButton = await page.getByText("Exit", { exact: true }).count();

  if (exitButton > 0) {
    await page.getByText("Exit", { exact: true }).click();
  }

  await page.getByTestId("icon-ChevronLeft").last().click();
  await page.getByTestId("home-dropdown-menu").nth(0).click();
  await page.getByTestId("btn-download-json").last().click();
  await page.waitForTimeout(1000);
  await page.getByText(/.*exported successfully/).isVisible();

  await page.getByText("Flows", { exact: true }).click();
  await page.getByTestId("home-dropdown-menu").nth(0).click();
  await page.getByTestId("btn-download-json").last().click();
  await page.waitForTimeout(1000);
  await page
    .getByText(/.*exported successfully/)
    .last()
    .isVisible();

  await page.getByText("Components", { exact: true }).click();
  await page.getByTestId("home-dropdown-menu").nth(0).click();
  await page.getByTestId("btn-download-json").last().click();
  await page.waitForTimeout(1000);
  await page
    .getByText(/.*exported successfully/)
    .last()
    .isVisible();
});

test("user should be able to upload a flow or a component", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

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

  await page.getByTestId("upload-folder-button").last().click();
});

test("user should be able to duplicate a flow or a component", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

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
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  await page.getByText("Chat Input", { exact: true }).click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.waitForTimeout(1000);

  if (await page.getByTestId("replace-button").isVisible()) {
    await page.getByTestId("replace-button").click();
  }

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  const exitButton = await page.getByText("Exit", { exact: true }).count();

  if (exitButton > 0) {
    await page.getByText("Exit", { exact: true }).click();
  }

  const replaceButton = await page.getByTestId("replace-button").isVisible();

  if (replaceButton) {
    await page.getByTestId("replace-button").click();
  }

  await page.getByTestId("icon-ChevronLeft").last().click();
  await page.getByTestId("home-dropdown-menu").nth(1).click();
  await page.getByTestId("btn-duplicate-flow").last().click();

  await page.waitForTimeout(1000);
  await page.getByText("Items duplicated successfully").isVisible();
});
