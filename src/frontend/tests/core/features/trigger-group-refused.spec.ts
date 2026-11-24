import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import {
  placeScheduleTrigger,
  searchPalette,
} from "../../utils/trigger-canvas";
import { installTriggerMocks } from "../../utils/trigger-mocks";

const GROUP_TRIGGER_MESSAGE = "Select non-trigger components only";

test(
  "grouping a selection that contains a trigger is refused",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const server = await installTriggerMocks(page);
    await placeScheduleTrigger(page, server, {
      triggerId: "trg-group-refused-e2e",
      flowName: "Grouped trigger",
    });

    await searchPalette(page, "parser");
    await page.getByTestId("add-component-button-parser").click();
    await adjustScreenView(page);

    await page
      .getByRole("button", { name: "Output handle for Event on node Schedule" })
      .click();
    await page
      .getByRole("button", {
        name: "Input handle for JSON or Table on node Parser",
      })
      .click();
    await expect(page.locator(".react-flow__edge")).toHaveCount(1);

    const nodes = page.locator(".react-flow__node");
    await expect(nodes).toHaveCount(2);
    const boxes = await Promise.all([
      nodes.nth(0).boundingBox(),
      nodes.nth(1).boundingBox(),
    ]);
    const [a, b] = boxes.map((box) => {
      expect(box, "canvas node should have a box").toBeTruthy();
      return box!;
    });
    await page.keyboard.down("Shift");
    await page.mouse.move(Math.min(a.x, b.x) - 40, Math.min(a.y, b.y) - 40);
    await page.mouse.down();
    await page.mouse.move(
      Math.max(a.x + a.width, b.x + b.width) + 40,
      Math.max(a.y + a.height, b.y + b.height) + 40,
      { steps: 10 },
    );
    await page.mouse.up();
    await page.keyboard.up("Shift");

    const groupButton = page.getByTestId("error-group-node");
    await expect(groupButton).toBeVisible({ timeout: TIMEOUTS.standard });
    await expect(groupButton).toBeDisabled();

    // The shortcut takes the same path as the button and says why it refused.
    await page.keyboard.press("ControlOrMeta+g");
    await expect(page.getByText("Invalid selection")).toBeVisible();
    await expect(page.getByText(GROUP_TRIGGER_MESSAGE)).toBeVisible();
    await expect(nodes).toHaveCount(2);
    await expect(page.getByTestId("title-Group")).toHaveCount(0);

    await page.runA11yScan("trigger-group-refused");
  },
);
