import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import {
  addParameterToNode,
  setParameterApiEditable,
} from "../../utils/open-advanced-options";

// LE-1810: API exposure is managed per-parameter on the node (panel API
// toggle backed by the persisted api_editable flag). The apiModal no longer
// hosts an "Input Schema" section — snippets derive from the exposed fields.

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

    // Expose a parameter through the node's parameters panel — the snippet
    // must pick it up as a tweak.
    await page.keyboard.press("Escape");
    await page.getByTestId("title-Language Model").click();
    await addParameterToNode(page, "stream");
    await setParameterApiEditable(page, "stream", true);

    await page.getByTestId("publish-button").click();
    await page.getByTestId("api-access-item").click();
    await page.getByTestId("api_tab_curl").click();
    await page.getByTestId("icon-Copy").click();
    const handle2 = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent2 = await handle2.jsonValue();
    const newValue = clipboardContent2;
    expect(oldValue).not.toBe(newValue);
    expect(newValue).toContain("stream");
    expect(clipboardContent2.length).toBeGreaterThan(clipboardContent.length);
  },
);

test("check if exposed parameters are updating when something on the flow changes", async ({
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

  // Expose both edited fields so the snippets carry their live values.
  await page.getByTestId("div-generic-node").click();
  await setParameterApiEditable(page, "collection_name", true);
  await setParameterApiEditable(page, "persist_directory", true);

  // biome-ignore lint/suspicious/noExplicitAny: legacy
  const focusElementsOnBoard = async ({ page }: any) => {
    const focusElements = await page.getByTestId("publish-button").first();
    await focusElements.click();
  };

  await focusElementsOnBoard({ page });

  await page.getByTestId("api-access-item").click();

  await page.getByText("Python", { exact: true }).click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();

  await page.getByText("JavaScript", { exact: true }).click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();

  await page.getByText("cURL", { exact: true }).click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();
});
