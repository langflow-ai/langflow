import { test } from "@playwright/test";

test("select and delete all", async ({ page }) => {
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

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.getByText("Select All").click();
  await page.getByText("Unselect All").isVisible();
  await page.getByTestId("icon-Trash2").click();
  await page.getByText("Delete").last().click();

  await page.waitForTimeout(1000);
  await page.getByText("Selected items deleted successfully").isVisible();
});

test("search flows", async ({ page }) => {
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

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.getByText("Select All").isVisible();
  await page.getByText("New Project", { exact: true }).click();
  await page.getByRole("heading", { name: "Memory Chatbot" }).click();
  await page.getByTestId("icon-ChevronLeft").first().click();
  await page.getByText("New Project", { exact: true }).click();
  await page.getByRole("heading", { name: "Document QA" }).click();
  await page.getByTestId("icon-ChevronLeft").first().click();
  await page.getByPlaceholder("Search flows").fill("Memory Chatbot");
  await page.getByText("Memory Chatbot", { exact: true }).isVisible();
  await page.getByText("Document QA", { exact: true }).isHidden();
  await page.getByText("Basic Prompting", { exact: true }).isHidden();
});

test("search components", async ({ page }) => {
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

  await page.getByText("Chat Input").first().click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.keyboard.press("Escape");
  await page
    .getByText("Prompt", {
      exact: true,
    })
    .first()
    .click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.keyboard.press("Escape");

  await page
    .getByText("OpenAI", {
      exact: true,
    })
    .first()
    .click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.keyboard.press("Escape");
  await page.getByTestId("icon-ChevronLeft").first().click();

  await page
    .getByText("Components", {
      exact: true,
    })
    .click();

  await page.getByPlaceholder("Search components").fill("Chat Input");
  await page.getByText("Chat Input", { exact: true }).isVisible();
  await page.getByText("Prompt", { exact: true }).isHidden();
  await page.getByText("OpenAI", { exact: true }).isHidden();
});

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
  await page.getByText("Chat Input", { exact: true }).click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.waitForTimeout(3000);

  if (await page.getByTestId("replace-button").isVisible()) {
    await page.getByTestId("replace-button").click();
  }
  await page.waitForTimeout(3000);

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
  await page.getByText("Chat Input", { exact: true }).click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.waitForTimeout(3000);

  if (await page.getByTestId("replace-button").isVisible()) {
    await page.getByTestId("replace-button").click();
  }
  await page.waitForTimeout(3000);

  await page.getByTestId("icon-ChevronLeft").last().click();
  await page.getByRole("checkbox").nth(1).click();

  await page.getByTestId("icon-Copy").last().click();
  await page.waitForTimeout(1000);
  await page.getByText("Items duplicated successfully").isVisible();
});
