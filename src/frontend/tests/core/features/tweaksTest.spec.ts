import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { TEXTS } from "../../utils/constants/texts";

test(
  "curl_api_generation",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page, context }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();
    // Wait for the new-flow Loading state to clear before checking the
    // publish button — the canvas mounts only after the flow finishes
    // loading, which can outlast a 20s action timeout on Windows CI.
    await page.waitForSelector('text="Loading"', {
      state: "hidden",
      timeout: 60000,
    });
    await page.waitForSelector('[data-testid="publish-button"]', {
      timeout: 30000,
    });
    await page.getByTestId("publish-button").click();
    await page.getByTestId("api-access-item").click();
    await page.getByTestId("api_tab_curl").click();
    await page.getByTestId("icon-Copy").click();
    const handle = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent = await handle.jsonValue();
    const oldValue = clipboardContent;
    expect(clipboardContent.length).toBeGreaterThan(0);
    await page.getByTestId("tweaks-button").click();
    await page
      .getByRole("heading", { name: TEXTS.componentLanguageModel })
      .locator("div")
      .first()
      .click();

    await page.waitForSelector('[data-testid="showstream"]', {
      timeout: 1000,
    });

    await page.getByTestId("showstream").first().click();

    await page.getByText(TEXTS.close).last().click();

    await page.getByTestId("api_tab_curl").click();
    await page.getByTestId("icon-Copy").click();
    const handle2 = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent2 = await handle2.jsonValue();
    const newValue = clipboardContent2;
    expect(oldValue).not.toBe(newValue);
    expect(clipboardContent2.length).toBeGreaterThan(clipboardContent.length);
    await awaitBootstrapTest(page, { skipModal: true });
    await page.getByText(TEXTS.templateBasicPrompting).first().click();
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

  await page.waitForSelector('[data-testid="chromaChroma DB"]', {
    timeout: 1000,
  });

  await page
    .getByTestId("chromaChroma DB")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await adjustScreenView(page, { numberOfZoomOut: 3 });

  await page.getByTestId("popover-anchor-input-collection_name").click();
  await page
    .getByTestId("popover-anchor-input-collection_name")
    .fill("collection_name_test_123123123!@#$&*(&%$@");

  await page.getByTestId("popover-anchor-input-persist_directory").click();
  await page
    .getByTestId("popover-anchor-input-persist_directory")
    .fill("persist_directory_123123123!@#$&*(&%$@");

  // biome-ignore lint/suspicious/noExplicitAny: legacy
  const focusElementsOnBoard = async ({ page }: any) => {
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

  await page.getByText(TEXTS.close).last().click();

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
