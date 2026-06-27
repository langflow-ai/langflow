import { expect } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { buildFlowAndWait } from "../../utils/flow/build-flow-and-wait";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

withEventDeliveryModes(
  "Blog Writer",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await openStarterProject(page, "Blog Writer");

    await initialGPTsetup(page);
    await buildFlowAndWait(page);

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await sendPlaygroundMessage(
      page,
      "https://www.natgeokids.com/uk/discover/animals/sea-life/turtle-facts/",
    );

    const textContents = await getAllResponseMessage(page);
    expect(textContents.length).toBeGreaterThan(100);
    expect(textContents).toContain("turtle");
  },
);
