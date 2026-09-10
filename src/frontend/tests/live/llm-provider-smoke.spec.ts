import { expect, test } from "../fixtures";
import { loadDotenvIfLocal } from "../utils/env/load-dotenv";
import { skipIfMissing } from "../utils/env/skip-if-missing";
import { buildFlowAndWait } from "../utils/flow/build-flow-and-wait";
import { openStarterProject } from "../utils/flow/open-starter-project";
import { initialGPTsetup } from "../utils/initialGPTsetup";
import { sendPlaygroundMessage } from "../utils/playground/send-playground-message";

test(
  "live OpenAI Basic Prompting reaches terminal success with output",
  { tag: ["@release", "@starter-projects"] },
  async ({ page }) => {
    loadDotenvIfLocal(__dirname);
    skipIfMissing.openAiKey();

    await openStarterProject(page, "Basic Prompting");
    await initialGPTsetup(page);
    await buildFlowAndWait(page);
    await page.getByRole("button", { name: "Playground", exact: true }).click();

    await sendPlaygroundMessage(
      page,
      "Reply with one short sentence confirming this provider smoke test.",
    );

    const output = page.getByTestId("div-chat-message").last();
    await expect(output).toBeVisible();
    await expect(output).not.toBeEmpty();
  },
);
