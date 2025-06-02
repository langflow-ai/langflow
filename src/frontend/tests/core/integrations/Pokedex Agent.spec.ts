import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Pokedex Agent",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Pokédex Agent" }).click();

    await initialGPTsetup(page);

    await page.getByTestId("playground-btn-flow-io").click();

    await page
      .getByTestId("input-chat-playground")
      .last()
      .fill("Can I catch a Charizard in Pokemon Yellow?");

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
    expect(output).toContain("Charmander");
    expect(output.length).toBeGreaterThan(100);
  },
);
