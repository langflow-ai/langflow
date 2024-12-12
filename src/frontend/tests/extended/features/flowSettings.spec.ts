import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "flowSettings",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="flow_name"]', {
      timeout: 3000,
    });

    await page.getByTestId("flow_name").click();
    await page.getByText("Flow Settings").first().click();
    await page
      .getByPlaceholder("Flow name")
      .fill(
        "Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test",
      );

    await page.getByText("Character limit reached").isVisible();

    await page.getByPlaceholder("Flow name").click();
    const randomName = Math.random().toString(36).substring(2);
    await page.getByPlaceholder("Flow name").fill(randomName);
    await page.getByPlaceholder("Flow name").click();
    await page
      .getByPlaceholder("Flow description")
      .fill(
        "Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test",
      );

    await page.getByTestId("save-flow-settings").click();

    await page.getByText("Changes saved successfully").isVisible();

    await page.getByTestId("flow_name").click();
    await page.getByText("Flow Settings").first().click();

    const flowName = await page.getByPlaceholder("Flow name").inputValue();
    const flowDescription = await page
      .getByPlaceholder("Flow description")
      .inputValue();

    if (flowName != randomName) {
      expect(false).toBeTruthy();
    }

    if (
      flowDescription !=
      "Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test"
    ) {
      expect(false).toBeTruthy();
    }
    await page.getByText("Saved").first().isVisible();
    await page.getByTestId("icon-CheckCircle2").first().isVisible();
  },
);
