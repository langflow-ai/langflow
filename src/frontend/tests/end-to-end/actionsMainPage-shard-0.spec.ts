import { test } from "@playwright/test";

test("user should be able to download a flow or a component", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page.getByText("Chat Input", { exact: true }).click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.waitForTimeout(3000);

  if (await page.getByTestId("replace-button").isVisible()) {
    await page.getByTestId("replace-button").click();
  }

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").last().click();
  await page.getByRole("checkbox").nth(1).click();
  await page.getByTestId("icon-FileDown").last().click();
  await page.waitForTimeout(1000);
  await page.getByText("Items exported successfully").isVisible();

  await page.getByText("Flows", { exact: true }).click();
  await page.getByRole("checkbox").nth(1).click();
  await page.getByTestId("icon-FileDown").last().click();
  await page.waitForTimeout(1000);
  await page.getByText("Items exported successfully").isVisible();

  await page.getByText("Components", { exact: true }).click();
  await page.getByRole("checkbox").nth(1).click();
  await page.getByTestId("icon-FileDown").last().click();
  await page.waitForTimeout(1000);
  await page.getByText("Components exported successfully").isVisible();
});

test("user should be able to upload a flow or a component", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForTimeout(2000);

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
  await page.waitForTimeout(2000);

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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page.getByText("Chat Input", { exact: true }).click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.waitForTimeout(3000);

  if (await page.getByTestId("replace-button").isVisible()) {
    await page.getByTestId("replace-button").click();
  }

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });
  await page.getByTestId("icon-ChevronLeft").last().click();
  await page.getByRole("checkbox").nth(1).click();

  await page.getByTestId("icon-Copy").last().click();
  await page.waitForTimeout(1000);
  await page.getByText("Items duplicated successfully").isVisible();
});
