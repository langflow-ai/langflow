import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import {
  closeParametersPanel,
  openParametersPanel,
  toggleParameterOnNode,
} from "../../utils/open-advanced-options";
import { unselectNodes } from "../../utils/unselect-nodes";

test(
  "user should not be able to hide connected inputs",
  { tag: ["@release", "@api", "@database"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await page.waitForSelector("text=Language Model", { timeout: 30000 });

    await page
      .getByTestId("div-generic-node")
      .getByText(TEXTS.componentLanguageModel, { exact: true })
      .click();
    await openParametersPanel(page);

    // LE-1810: connected fields stay listed in the panel, but their
    // visibility cannot be changed while the handle is connected.
    await expect(
      page.getByTestId("inspector-remove-input_value"),
    ).toBeDisabled();

    await closeParametersPanel(page);

    await page.locator(".react-flow__edge").nth(0).click();

    await page.keyboard.press("Delete");

    await expect(page.locator(".react-flow__edge")).toHaveCount(2);

    await page
      .getByTestId("div-generic-node")
      .getByText(TEXTS.componentLanguageModel, { exact: true })
      .click();
    await openParametersPanel(page);

    // After disconnecting, the parameter can be managed again
    await expect(
      page.getByTestId("inspector-remove-input_value"),
    ).toBeEnabled();

    await toggleParameterOnNode(page, "input_value");
    await expect(page.getByTestId("inspector-add-input_value")).toBeVisible();

    await closeParametersPanel(page);

    await unselectNodes(page);

    await expect(page.getByText("Input", { exact: true })).toBeHidden();
  },
);

test(
  "user should see why a connected input cannot be hidden",
  { tag: ["@release", "@api", "@database"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await page.waitForSelector("text=Language Model", { timeout: 30000 });

    await page
      .getByTestId("div-generic-node")
      .getByText(TEXTS.componentLanguageModel, { exact: true })
      .click();
    await openParametersPanel(page);

    const removeInputValue = page.getByTestId("inspector-remove-input_value");
    await expect(removeInputValue).toBeVisible();

    await expect(removeInputValue).toBeDisabled();

    // The disabled button is pointer-events-none (so the tooltip reaches
    // real users through its wrapper) — hover the wrapper, not the button.
    await page.getByTestId("inspector-remove-wrapper-input_value").hover();

    await expect(
      page.getByText("Cannot change visibility of connected handles"),
    ).toBeVisible();

    await closeParametersPanel(page);

    await page.locator(".react-flow__edge").nth(0).click();

    await page.keyboard.press("Delete");

    await expect(page.locator(".react-flow__edge")).toHaveCount(2);

    await page
      .getByTestId("div-generic-node")
      .getByText(TEXTS.componentLanguageModel, { exact: true })
      .click();
    await openParametersPanel(page);

    await expect(removeInputValue).toBeEnabled();

    await toggleParameterOnNode(page, "input_value");
    await expect(page.getByTestId("inspector-add-input_value")).toBeVisible();

    await closeParametersPanel(page);

    await expect(page.getByText("Input", { exact: true })).toBeHidden();
  },
);
