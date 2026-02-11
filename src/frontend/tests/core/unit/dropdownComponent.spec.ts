import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  closeAdvancedOptions,
  disableInspectPanel,
  enableInspectPanel,
  openAdvancedOptions,
} from "../../utils/open-advanced-options";

test(
  "dropDownComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    // Allow for legacy components
    await page.getByTestId("sidebar-options-trigger").click();
    await page.getByTestId("sidebar-legacy-switch").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("amazon");

    await page.waitForSelector('[data-testid="amazonAmazon Bedrock"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("amazonAmazon Bedrock")
      .first()
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    await page.waitForTimeout(1000);

    await page.getByTestId("title-Amazon Bedrock").click();

    await page.getByTestId("dropdown_str_model_id").click();

    await page
      .getByTestId(/anthropic\.claude-3-haiku-20240307-v1:0.*option/)
      .click();

    let value = await page
      .getByTestId(/anthropic\.claude-3-haiku-20240307-v1:0.*option/)
      .first()
      .innerText();
    if (value !== "anthropic.claude-3-haiku-20240307-v1:0") {
      expect(false).toBeTruthy();
    }

    await page.waitForTimeout(1000);

    await adjustScreenView(page);

    await page.getByTestId("dropdown_str_model_id").click();
    await page.getByText("anthropic.claude-v2").last().click();

    await page.waitForTimeout(1000);

    value = await page.getByTestId("dropdown_str_model_id").innerText();
    expect(value.length).toBeGreaterThan(10);

    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 3000,
    });

    await page.waitForTimeout(1000);

    value = await page
      .getByTestId("value-dropdown-dropdown_str_model_id")
      .innerText();

    expect(value.length).toBeGreaterThan(10);

    await page.getByTestId("keypair0").fill("test1");
    await page.getByTestId("keypair100").fill("test2");


        await page.locator(".react-flow__renderer").click();

    await page.waitForTimeout(1000);

    await page.getByTestId("title-Amazon Bedrock").click();

    const valueKeyPair0 = await page.getByTestId("keypair0").inputValue();
    const valueKeyPair100 = await page.getByTestId("keypair100").inputValue();

    expect(valueKeyPair0).toBe("test1");
    expect(valueKeyPair100).toBe("test2");

  },
);
