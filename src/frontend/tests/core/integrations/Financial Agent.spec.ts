import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Financial Agent",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.TAVILY_API_KEY,
      "TAVILY_API_KEY required to run this test",
    );

    test.skip(
      !process?.env?.SAMBANOVA_API_KEY,
      "SAMBANOVA_API_KEY required to run this test",
    );

    await page.goto("/");
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Financial Agent" }).click();

    await page
      .getByTestId("popover-anchor-input-api_key")
      .nth(0)
      .fill(process.env.TAVILY_API_KEY ?? "");

    for (let i = 0; i < 2; i++) {
      await page.getByTestId("dropdown_str_agent_llm").nth(i).click();
      await page.waitForTimeout(500);
      await page.getByRole("option", { name: "SambaNova" }).click();
    }

    for (let i = 0; i < 3; i++) {
      await page
        .getByTestId("value-dropdown-dropdown_str_model_name")
        .nth(i)
        .click();
      await page.waitForTimeout(500);

      await page.getByRole("option").first().click();
    }

    for (let i = 1; i <= 3; i++) {
      await page
        .getByTestId("popover-anchor-input-api_key")
        .nth(i)
        .fill(process.env.SAMBANOVA_API_KEY ?? "");
    }

    await page.getByTestId("playground-btn-flow-io").click();

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("Why did Nvidia stock drop in January?");

    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: "Stop" });
    await stopButton.waitFor({ state: "visible", timeout: 30000 });

    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 120000 });
    }

    const output = await page
      .getByTestId("div-chat-message")
      .last()
      .innerText();
    expect(output.toLowerCase()).toContain("nvidia");
    expect(output.length).toBeGreaterThan(100);
  },
);
