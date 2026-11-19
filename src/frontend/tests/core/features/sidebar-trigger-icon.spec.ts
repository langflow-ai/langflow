import { expect, test } from "../../fixtures";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

test(
  "sidebar marks a provider's triggers apart from its actions, with no grip icon",
  { tag: ["@release", "@components", "@workspace"] },
  async ({ page }) => {
    await openBlankFlow(page);

    await page.getByTestId("sidebar-search-input").fill("slack");
    const trigger = page.getByTestId("slack_slack: on message_draggable");
    const action = page.getByTestId(
      "slack_slack: send message (as user)_draggable",
    );
    await expect(trigger).toBeVisible({ timeout: 30000 });
    await expect(action).toBeVisible();

    await expect(trigger.getByTestId("sidebar-trigger-icon")).toBeVisible();
    await expect(action.getByTestId("sidebar-trigger-icon")).toHaveCount(0);
    await expect(
      page
        .locator('[data-testid$="_draggable"]')
        .locator('[data-testid="icon-GripVertical"]'),
    ).toHaveCount(0);

    await action.hover();
    await expect(
      action.getByTestId("add-component-button-slack:-send-message-(as-user)"),
    ).toBeVisible();
    await page.runA11yScan("sidebar-trigger-and-action-rows");
  },
);
