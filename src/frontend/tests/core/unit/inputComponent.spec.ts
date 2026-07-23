import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import {
  closeParametersPanel,
  openParametersPanel,
  toggleParameterOnNode,
} from "../../utils/open-advanced-options";

test(
  "InputComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("Chroma");

    await page.waitForSelector('[data-testid="chromaChroma DB"]', {
      timeout: 3000,
    });
    await page
      .getByTestId("chromaChroma DB")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    await page.getByTestId("popover-anchor-input-collection_name").click();
    await page
      .getByTestId("popover-anchor-input-collection_name")
      .fill("collection_name_test_123123123!@#$&*(&%$@");

    const value = await page
      .getByTestId("popover-anchor-input-collection_name")
      .inputValue();

    if (value != "collection_name_test_123123123!@#$&*(&%$@") {
      expect(false).toBeTruthy();
    }

    // Test cursor position preservation
    const input = page.getByTestId("popover-anchor-input-collection_name");
    await input.click();
    await input.press("Home"); // Move cursor to start
    await input.press("ArrowRight"); // Move cursor to position 1
    await input.press("ArrowRight"); // Move cursor to position 2
    await input.pressSequentially("X", { delay: 100 }); // Type at position 2
    const cursorValue = await input.inputValue();
    if (!cursorValue.startsWith("coX")) {
      expect(false).toBeTruthy();
    }
    await input.fill("collection_name_test_123123123!@#$&*(&%$@");

    await page.getByTestId("div-generic-node").click();

    // LE-1810: canvas visibility rounds now happen through the panel
    // Add/Remove rows.
    await openParametersPanel(page);

    await toggleParameterOnNode(page, "chroma_server_cors_allow_origins");
    await expect(
      page.getByTestId("inspector-remove-chroma_server_cors_allow_origins"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "chroma_server_grpc_port");
    await expect(
      page.getByTestId("inspector-remove-chroma_server_grpc_port"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "chroma_server_host");
    await expect(
      page.getByTestId("inspector-remove-chroma_server_host"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "chroma_server_http_port");
    await expect(
      page.getByTestId("inspector-remove-chroma_server_http_port"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "chroma_server_ssl_enabled");
    await expect(
      page.getByTestId("inspector-remove-chroma_server_ssl_enabled"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "chroma_server_cors_allow_origins");
    await expect(
      page.getByTestId("inspector-add-chroma_server_cors_allow_origins"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "chroma_server_grpc_port");
    await expect(
      page.getByTestId("inspector-add-chroma_server_grpc_port"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "chroma_server_host");
    await expect(
      page.getByTestId("inspector-add-chroma_server_host"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "chroma_server_http_port");
    await expect(
      page.getByTestId("inspector-add-chroma_server_http_port"),
    ).toBeVisible();

    await toggleParameterOnNode(page, "chroma_server_ssl_enabled");
    await expect(
      page.getByTestId("inspector-add-chroma_server_ssl_enabled"),
    ).toBeVisible();

    await closeParametersPanel(page);

    // LE-1810: the value stays editable on the node itself.
    const valueEditNode = await page
      .getByTestId("popover-anchor-input-collection_name")
      .inputValue();

    if (valueEditNode != "collection_name_test_123123123!@#$&*(&%$@") {
      expect(false).toBeTruthy();
    }

    await page
      .getByTestId("popover-anchor-input-collection_name")
      .fill("NEW_collection_name_test_123123123!@#$&*(&%$@ÇÇÇÀõe");

    const plusButtonLocator = page.getByTestId("input-collection_name");
    const elementCount = await plusButtonLocator?.count();
    if (elementCount === 0) {
      expect(true).toBeTruthy();

      await page.getByTestId("div-generic-node").click();

      await openParametersPanel(page);

      await closeParametersPanel(page);

      const value = await page
        .getByTestId("popover-anchor-input-collection_name")
        .inputValue();

      if (value != "NEW_collection_name_test_123123123!@#$&*(&%$@ÇÇÇÀõe") {
        expect(false).toBeTruthy();
      }
    }
  },
);
