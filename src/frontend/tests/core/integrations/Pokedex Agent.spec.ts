import { expect, test } from "../../fixtures";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { openStarterProject } from "../../utils/flow/open-starter-project";

import { TEXTS } from "../../utils/constants/texts";
withEventDeliveryModes(
  "Pokedex Agent",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await openStarterProject(page, "Pokédex Agent");

    await initialGPTsetup(page);

    await page.getByTestId("playground-btn-flow-io").click();

    await expect(page.getByTestId("input-chat-playground")).toBeVisible();
    await page.getByTestId("input-chat-playground").click();
    await page
      .getByTestId("input-chat-playground")
      .fill("Can I catch a Charizard in Pokemon Yellow?");

    await page.getByTestId("button-send").last().click();

    const stopButton = page.getByRole("button", { name: TEXTS.stop });
    await stopButton.waitFor({ state: "visible", timeout: 40000 });

    if (await stopButton.isVisible()) {
      await expect(stopButton).toBeHidden({ timeout: 200000 });
    }

    const output = await page
      .getByTestId("div-chat-message")
      .last()
      .innerText();
    expect(output).toContain("Charmander");
    expect(output.length).toBeGreaterThan(50);
  },
);
