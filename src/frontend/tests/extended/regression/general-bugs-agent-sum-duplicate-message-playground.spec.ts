import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";

test(
  "user must not experience message duplication in mathematical expressions with agent component",
  { tag: ["@release", "@components", "@workspace"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateSimpleAgent })
      .first()
      .click();

    await configureLoopbackOpenAI(page);

    await page.getByTestId(TID.playgroundBtnFlowIo).click();
    await sendPlaygroundMessage(page, "2+2");

    const calculatorTrigger = page.getByRole("button", {
      name: /calculator|evaluate expression/i,
    });
    await expect(calculatorTrigger).toBeVisible({
      timeout: TIMEOUTS.buildComplete,
    });
    await expect(
      calculatorTrigger.getByTestId("tool-status-done"),
    ).toBeVisible();
    if ((await calculatorTrigger.getAttribute("data-state")) !== "open") {
      await calculatorTrigger.click();
    }
    const calculatorCard = page.getByRole("region", {
      name: /tool done (calculator|evaluate expression)/i,
    });

    // The current tool card renders primitive arguments as labelled rows,
    // rather than the legacy JSON tabs. Assert the calculator saw exactly one
    // expression and produced the corresponding result.
    await expect(
      calculatorCard.getByText("expression", { exact: true }),
    ).toBeVisible();
    await expect(
      calculatorCard.getByText('"2+2"', { exact: true }),
    ).toBeVisible();
    await expect(calculatorCard.locator("code")).toContainText(
      /"result"\s*:\s*"4"/,
    );
    await expect(
      calculatorCard.getByText('"2+22+2"', { exact: true }),
    ).toHaveCount(0);
    await expect(
      calculatorCard.getByText('"22+2"', { exact: true }),
    ).toHaveCount(0);
    await expect(calculatorCard.locator("code")).not.toContainText(
      /"result"\s*:\s*"26"/,
    );
  },
);
