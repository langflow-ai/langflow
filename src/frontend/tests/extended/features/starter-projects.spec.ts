import { type Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to interact with starter projects",
  { tag: ["@release", "@starter-projectss"] },
  async ({ page, context }) => {
    await awaitBootstrapTest(page);

    expect(page.getByText("Start from scratch", { exact: true })).toBeVisible();
    expect(page.getByRole("button", { name: "Blank Flow" })).toBeVisible();

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.waitForSelector('[data-testid="search-input-template"]', {
      timeout: 3000,
    });

    await page.getByTestId("search-input-template").fill("Document");

    await page.waitForTimeout(1000);

    expect(
      page.getByTestId("template_basic-prompting-(hello,-world)"),
    ).toBeVisible({ visible: false, timeout: 3000 });

    expect(page.getByTestId("template_document-q&a").first()).toBeVisible();
    expect(
      page.getByTestId(`template_sequential-tasks-agents`).first(),
    ).toBeVisible();

    expect(page.getByTestId("template_vector-store")).not.toBeVisible();
    expect(page.getByTestId(`template_simple-agent`)).not.toBeVisible();
    expect(page.getByTestId(`template_dynamic-agent`)).not.toBeVisible();
    expect(
      page.getByTestId(`template_hierarchical-tasks-agent`),
    ).not.toBeVisible();

    await page.getByTestId(`side_nav_options_prompting`).click();
    expect(page.getByTestId(`category_title_prompting`)).toBeVisible({
      timeout: 3000,
    });

    await page.getByTestId(`side_nav_options_rag`).click();

    expect(page.getByTestId(`category_title_rag`)).toBeVisible({
      timeout: 3000,
    });
    expect(page.getByTestId(`template_vector-store-rag`)).toBeVisible();

    expect(
      page.getByTestId(`template_basic-prompting-(hello,-world)`),
    ).not.toBeVisible();
    expect(page.getByTestId(`template_document-qa`)).not.toBeVisible();

    await page.getByTestId(`side_nav_options_agents`).click();

    expect(page.getByTestId(`category_title_agents`)).toBeVisible({
      timeout: 3000,
    });
    expect(
      page.getByTestId(`template_basic-prompting-(hello,-world)`),
    ).toBeVisible({ visible: false, timeout: 3000 });
    expect(page.getByTestId(`template_document-qa`)).not.toBeVisible();
    expect(page.getByTestId(`template_vector-store-rag`)).not.toBeVisible();

    await waitForTemplateVisibility(page, templateIds);
  },
);

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
  "template_instagram-copywriter",
  "template_saas-pricing",
  "template_travel-planning-agents",
  "template_research-agent",
  "template_simple-agent",
  "template_sequential-tasks-agents",
  "template_market-research",
];
