import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { enableInspectPanel } from "../../utils/open-advanced-options";

test(
  "InputComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
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

    await enableInspectPanel(page);

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("edit-fields-button").click();

    await page
      .locator('//*[@id="showchroma_server_cors_allow_origins"]')
      .click();
    expect(
      await page
        .locator('//*[@id="showchroma_server_cors_allow_origins"]')
        .isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showchroma_server_grpc_port"]').click();
    expect(
      await page.locator('//*[@id="showchroma_server_grpc_port"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showchroma_server_host"]').click();
    expect(
      await page.locator('//*[@id="showchroma_server_host"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showchroma_server_http_port"]').click();
    expect(
      await page.locator('//*[@id="showchroma_server_http_port"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showchroma_server_ssl_enabled"]').click();
    expect(
      await page
        .locator('//*[@id="showchroma_server_ssl_enabled"]')
        .isChecked(),
    ).toBeTruthy();

    await page
      .locator('//*[@id="showchroma_server_cors_allow_origins"]')
      .click();
    expect(
      await page
        .locator('//*[@id="showchroma_server_cors_allow_origins"]')
        .isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showchroma_server_grpc_port"]').click();
    expect(
      await page.locator('//*[@id="showchroma_server_grpc_port"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showchroma_server_host"]').click();
    expect(
      await page.locator('//*[@id="showchroma_server_host"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showchroma_server_http_port"]').click();
    expect(
      await page.locator('//*[@id="showchroma_server_http_port"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showchroma_server_ssl_enabled"]').click();
    expect(
      await page
        .locator('//*[@id="showchroma_server_ssl_enabled"]')
        .isChecked(),
    ).toBeFalsy();

    // Exit edit fields mode
    await page.getByTestId("edit-fields-button").click();

    // Verify canvas value is still correct after toggling field visibility
    const valueAfterToggles = await page
      .getByTestId("popover-anchor-input-collection_name")
      .inputValue();

    if (valueAfterToggles != "collection_name_test_123123123!@#$&*(&%$@") {
      expect(false).toBeTruthy();
    }

    // Fill new value on canvas and verify it persists
    await page
      .getByTestId("popover-anchor-input-collection_name")
      .fill("NEW_collection_name_test_123123123!@#$&*(&%$@ÇÇÇÀõe");

    const newValue = await page
      .getByTestId("popover-anchor-input-collection_name")
      .inputValue();

    if (newValue != "NEW_collection_name_test_123123123!@#$&*(&%$@ÇÇÇÀõe") {
      expect(false).toBeTruthy();
    }
  },
);
