import { expect } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { loadDotenvIfLocal } from "../../utils/env/load-dotenv";
import { skipIfMissing } from "../../utils/env/skip-if-missing";
import { buildFlowAndWait } from "../../utils/flow/build-flow-and-wait";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { getAllResponseMessage } from "../../utils/get-all-response-message";
import { initialGPTsetup } from "../../utils/initialGPTsetup";
import {
  waitForOpenModalWithChatInput,
  waitForOpenModalWithoutChatInput,
} from "../../utils/wait-for-open-modal";
import { withEventDeliveryModes } from "../../utils/withEventDeliveryModes";

// Auto-run starter templates that share one shape: open the template, apply the
// GPT setup, build/run, open the playground, and assert the generated output is
// long enough and contains the expected substrings. Each template stays its own
// test (per-failure clarity); the open/build/modal specifics differ per template
// so they are encoded as data rather than collapsed away.
type AutorunTemplate = {
  name: string;
  /** "starter" opens via openStarterProject; "heading" via the templates modal. */
  open?: "starter" | "heading";
  /** "build-and-wait" uses buildFlowAndWait; "run-button" clicks run + waits toast. */
  build?: "run-button" | "build-and-wait";
  /** Whether the playground modal carries a chat input. */
  modal?: "with-input" | "without-input";
  /** Some templates must expand the Chat Output node before building. */
  expandChatOutput?: boolean;
  minLength: number;
  contains?: string[];
};

const TEMPLATES: AutorunTemplate[] = [
  {
    name: "Prompt Chaining",
    build: "run-button",
    modal: "with-input",
    minLength: 100,
  },
  { name: "SEO Keyword Generator", minLength: 200, contains: ["work"] },
  {
    name: "SaaS Pricing",
    minLength: 100,
    contains: ["costs", "subscription"],
  },
  {
    name: "Twitter Thread Generator",
    open: "heading",
    expandChatOutput: true,
    minLength: 100,
    contains: ["langflow"],
  },
];

for (const template of TEMPLATES) {
  withEventDeliveryModes(
    template.name,
    { tag: ["@release", "@starter-projects"] },
    async ({ page }) => {
      loadDotenvIfLocal(__dirname);
      skipIfMissing.openAiKey();
      await page.goto("/");

      if ((template.open ?? "starter") === "heading") {
        await awaitBootstrapTest(page);
        await page.getByTestId("side_nav_options_all-templates").click();
        await page.getByRole("heading", { name: template.name }).click();
      } else {
        await openStarterProject(page, template.name);
      }

      await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
        timeout: 100000,
      });

      await initialGPTsetup(page);

      if (template.expandChatOutput) {
        await page.getByTestId("title-Chat Output").click();
        await page.getByTestId("icon-MoreHorizontal").click();
        await page.getByText("Expand").click();
      }

      if ((template.build ?? "build-and-wait") === "run-button") {
        await page.getByTestId("button_run_chat output").click();
        await page.waitForSelector(`text=${TEXTS.toastBuiltSuccessfully}`, {
          timeout: 60000,
        });
      } else {
        await buildFlowAndWait(page);
      }

      await page
        .getByRole("button", { name: TEXTS.playground, exact: true })
        .click();
      await page
        .getByText(TEXTS.labelNoInputMessage, { exact: true })
        .last()
        .isVisible();

      if ((template.modal ?? "without-input") === "with-input") {
        await waitForOpenModalWithChatInput(page);
      } else {
        await waitForOpenModalWithoutChatInput(page);
      }

      const textContents = await getAllResponseMessage(page);
      expect(textContents.length).toBeGreaterThan(template.minLength);
      for (const substring of template.contains ?? []) {
        expect(textContents).toContain(substring);
      }
    },
  );
}
