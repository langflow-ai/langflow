import { expect, Page, test } from "@playwright/test";

test("user must be able to interact with starter projects", async ({
  page,
  context,
}) => {
  await page.goto("/");
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

  expect(page.getByText("Start from scratch", { exact: true })).toBeVisible();
  expect(page.getByRole("button", { name: "Blank Flow" })).toBeVisible();

  await page.getByTestId("side_nav_options_all-templates").click();
  await page.waitForTimeout(500);

  await page.getByPlaceholder("Search...").fill("Document");
  await page.waitForTimeout(500);

  expect(
    page.getByTestId("template_basic-prompting-(hello,-world)"),
  ).not.toBeVisible();

  expect(page.getByTestId("template_document-qa").first()).toBeVisible();
  expect(
    page.getByTestId(`template_sequential-tasks-agent`).first(),
  ).toBeVisible();

  expect(page.getByTestId("template_vector-store")).not.toBeVisible();
  expect(page.getByTestId(`template_simple-agent`)).not.toBeVisible();
  expect(page.getByTestId(`template_dynamic-agent`)).not.toBeVisible();
  expect(
    page.getByTestId(`template_hierarchical-tasks-agent`),
  ).not.toBeVisible();

  await page.waitForTimeout(500);

  await page.getByTestId(`side_nav_options_prompting`).click();
  await page.waitForTimeout(500);
  expect(page.getByTestId(`category_title_prompting`)).toBeVisible();

  await page.getByTestId(`side_nav_options_rag`).click();
  await page.waitForTimeout(500);

  expect(page.getByTestId(`category_title_rag`)).toBeVisible();
  expect(page.getByTestId(`template_vector-store-rag`)).toBeVisible();

  expect(
    page.getByTestId(`template_basic-prompting-(hello,-world)`),
  ).not.toBeVisible();
  expect(page.getByTestId(`template_document-qa`)).not.toBeVisible();

  await page.getByTestId(`side_nav_options_agents`).click();
  await page.waitForTimeout(500);

  expect(page.getByTestId(`category_title_agents`)).toBeVisible();

  await page.waitForTimeout(500);

  expect(
    page.getByTestId(`template_basic-prompting-(hello,-world)`),
  ).not.toBeVisible();
  expect(page.getByTestId(`template_document-qa`)).not.toBeVisible();
  expect(page.getByTestId(`template_vector-store-rag`)).not.toBeVisible();

  await page.waitForTimeout(500);

  await waitForTemplateVisibility(page, templateIds);
});

async function waitForTemplateVisibility(page: Page, templateIds: string[]) {
  const timeout = 10000; // Increased timeout for better reliability

  for (const templateId of templateIds) {
    // Wait for the element to be attached to DOM first
    await page.waitForSelector(`[data-testid="${templateId}"]`, {
      state: "attached",
      timeout,
    });

    // Wait for the element to be visible
    await expect(
      page.getByTestId(templateId).last(),
      `Template ${templateId} should be visible`,
    ).toBeVisible({
      timeout,
    });

    // Optional: Ensure element is in viewport
    const element = page.getByTestId(templateId).last();
    await element.scrollIntoViewIfNeeded();
  }
}

// Your test code
const templateIds = [
  "template_travel-planning-agents",
  "template_sequential-tasks-agent",
  "template_dynamic-agent",
  "template_hierarchical-tasks-agent",
  "template_simple-agent",
];
