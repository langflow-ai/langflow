import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "curl_api_generation",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page, context }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.getByTestId("publish-button").click();
    await page.getByTestId("api-access-item").click();
    await page.getByRole("tab", { name: "cURL" }).click();
    await page.getByTestId("icon-Copy").click();
    const handle = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent = await handle.jsonValue();
    const oldValue = clipboardContent;
    expect(clipboardContent.length).toBeGreaterThan(0);
    await page.getByTestId("tweaks-button").click();
    await page
      .getByRole("heading", { name: "OpenAi" })
      .locator("div")
      .first()
      .click();

    await page.waitForSelector('[data-testid="showstream"]', {
      timeout: 1000,
    });

    await page.getByTestId("showstream").first().click();

    await page.getByText("Close").last().click();

    await page.getByRole("tab", { name: "cURL" }).click();
    await page.getByTestId("icon-Copy").click();
    const handle2 = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent2 = await handle2.jsonValue();
    const newValue = clipboardContent2;
    expect(oldValue).not.toBe(newValue);
    expect(clipboardContent2.length).toBeGreaterThan(clipboardContent.length);
    await awaitBootstrapTest(page, { skipModal: true });
    await page.getByText("Basic Prompting").first().click();
    await page.getByTestId("publish-button").click();
    await page.getByTestId("api-access-item").click();
    expect(
      await page.getByText("Input Schema (1)", { exact: true }).isVisible(),
    );
  },
);

test("check if tweaks are updating when someothing on the flow changes", async ({
  page,
}) => {
  await awaitBootstrapTest(page);

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });

  await page.getByTestId("blank-flow").click();
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("Chroma");

  await page.waitForSelector('[data-testid="vectorstoresChroma DB"]', {
    timeout: 1000,
  });

  await page
    .getByTestId("vectorstoresChroma DB")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("popover-anchor-input-collection_name").click();
  await page
    .getByTestId("popover-anchor-input-collection_name")
    .fill("collection_name_test_123123123!@#$&*(&%$@");

  await page.getByTestId("popover-anchor-input-persist_directory").click();
  await page
    .getByTestId("popover-anchor-input-persist_directory")
    .fill("persist_directory_123123123!@#$&*(&%$@");

  const focusElementsOnBoard = async ({ page }) => {
    const focusElements = await page.getByTestId("publish-button").first();
    await focusElements.click();
  };

  await focusElementsOnBoard({ page });

  await page.getByTestId("api-access-item").click();

  await page.getByTestId("tweaks-button").click();

  await page
    .getByRole("heading", { name: "Chroma" })
    .locator("div")
    .first()
    .click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();

  await page.getByText("Close").last().click();

  await page.getByText("Python", { exact: true }).click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();

  await page.getByText("JavaScript", { exact: true }).click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();

  await page.getByText("cURL", { exact: true }).click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();

  expect(await page.getByText("Input Schema (2)", { exact: true }).isVisible());
});
