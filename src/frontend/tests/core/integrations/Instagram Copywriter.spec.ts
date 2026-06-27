import { expect, test } from "../../fixtures";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { buildFlowAndWait } from "../../utils/flow/build-flow-and-wait";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";

test(
  "Instagram Copywriter",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    skipIfMissing.openAiKey();
    loadDotenvIfLocal(__dirname);
    await page.goto("/");
    await openStarterProject(page, "Instagram Copywriter");

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 100000,
    });

    await initialGPTsetup(page);
    await buildFlowAndWait(page);

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
    await sendPlaygroundMessage(
      page,
      "Create a Langflow post about visual AI workflow builders.",
    );

    const textContents = await getAllResponseMessage(page);

    expect(textContents.length).toBeGreaterThan(150);
  },
);
