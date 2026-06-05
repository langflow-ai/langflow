import { expect, test } from "../../fixtures";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { renameFlow } from "../../utils/rename-flow";

test(
  "flowSettings",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);

    await page.getByTestId("flow_name").isVisible({ timeout: 3000 });
    await page.getByTestId("flow_name").click();
    await page.waitForTimeout(500);

    await page.getByTestId("input-flow-name").click();

    await page
      .getByTestId("input-flow-name")
      .fill(
        "Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test",
      );

    await expect(page.getByText("Character limit reached")).toBeVisible();
    await page.getByTestId("input-flow-name").click();
    const randomName = Math.random().toString(36).substring(2);
    await page.getByTestId("input-flow-name").fill(randomName);
    await page
      .getByTestId("input-flow-description")
      .fill(
        "Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test",
      );

    await page.getByTestId("save-flow-settings").isEnabled({ timeout: 3000 });
    await page.getByTestId("save-flow-settings").click();

    await page
      .getByText("Changes saved successfully")
      .last()
      .isVisible({ timeout: 3000 });
    await page.getByText("Changes saved successfully").last().click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    const { flowName, flowDescription } = await renameFlow(page);

    expect(flowName == randomName).toBeTruthy();

    expect(
      flowDescription ==
        "Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name Test Flow Name ",
    ).toBeTruthy();
  },
);
