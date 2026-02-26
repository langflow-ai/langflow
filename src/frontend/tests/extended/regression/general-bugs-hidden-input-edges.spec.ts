import * as dotenv from "dotenv";
import path from "path";
import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import {
  closeAdvancedOptions,
  disableInspectPanel,
  enableInspectPanel,
  openAdvancedOptions,
} from "../../utils/open-advanced-options";
import { unselectNodes } from "../../utils/unselect-nodes";

test(
  "user should not be able to hide connected inputs",
  { tag: ["@release", "@api", "@database"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector("text=Language Model", { timeout: 30000 });

    await page
      .getByTestId("div-generic-node")
      .getByText("Language Model", { exact: true })
      .click();
    await openAdvancedOptions(page);

    const input_value = page.getByTestId("showinput_value");

    // Connected fields should not appear in edit mode
    await expect(input_value).toBeHidden();

    await closeAdvancedOptions(page);

    await page.locator(".react-flow__edge").nth(0).click();

    await page.keyboard.press("Delete");

    await expect(page.locator(".react-flow__edge")).toHaveCount(2);

    await page
      .getByTestId("div-generic-node")
      .getByText("Language Model", { exact: true })
      .click();
    await openAdvancedOptions(page);

    // After disconnecting, the field should appear and be enabled
    await expect(input_value).toBeVisible();
    await expect(input_value).toBeEnabled();

    await input_value.click();

    await closeAdvancedOptions(page);

    await unselectNodes(page);

    await expect(page.getByText("Input", { exact: true })).toBeHidden();
  },
);

test(
  "user should not be able to hide connected inputs when inspection panel is disabled",
  { tag: ["@release", "@api", "@database"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await disableInspectPanel(page);

    await page.waitForSelector("text=Language Model", { timeout: 30000 });

    await page
      .getByTestId("div-generic-node")
      .getByText("Language Model", { exact: true })
      .click();
    await openAdvancedOptions(page);

    const input_value = page.getByTestId("showinput_value");
    await expect(input_value).toBeVisible();

    await expect(input_value).toBeDisabled();

    await input_value.hover();

    await expect(
      page.getByText("Cannot change visibility of connected handles"),
    ).toBeVisible();

    await closeAdvancedOptions(page);

    await page.locator(".react-flow__edge").nth(0).click();

    await page.keyboard.press("Delete");

    await expect(page.locator(".react-flow__edge")).toHaveCount(2);

    await page
      .getByTestId("div-generic-node")
      .getByText("Language Model", { exact: true })
      .click();
    await openAdvancedOptions(page);

    await expect(input_value).toBeEnabled();

    await input_value.click();

    await closeAdvancedOptions(page);

    await expect(page.getByText("Input", { exact: true })).toBeHidden();

    await enableInspectPanel(page);
  },
);
