import { expect, test } from "@playwright/test";

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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  expect(page.getByText("Start from scratch")).toBeVisible();
  expect(
    page.getByRole("button", { name: "Create Blank Project" }),
  ).toBeVisible();

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

  await page.getByTestId(`side_nav_options_chatbots`).click();
  await page.waitForTimeout(500);
  expect(page.getByTestId(`category_title_chatbots`)).toBeVisible();

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

  expect(
    page.getByTestId(`template_basic-prompting-(hello,-world)`),
  ).not.toBeVisible();
  expect(page.getByTestId(`template_document-qa`)).not.toBeVisible();
  expect(page.getByTestId(`template_vector-store-rag`)).not.toBeVisible();

  expect(page.getByTestId(`template_travel-planning-agents`)).toBeVisible();
  expect(page.getByTestId(`template_sequential-tasks-agent`)).toBeVisible();
  expect(page.getByTestId(`template_dynamic-agent`)).toBeVisible();
  expect(page.getByTestId(`template_hierarchical-tasks-agent`)).toBeVisible();
  expect(page.getByTestId(`template_simple-agent`)).toBeVisible();
});
