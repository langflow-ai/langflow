import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { navigateSettingsPages } from "../../utils/go-to-settings";

test(
  "should scroll the provider list so every provider can be reached",
  { tag: ["@release", "@components", "@workspace"] },
  async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 680 });
    await awaitBootstrapTest(page, { skipModal: true });
    await navigateSettingsPages(page, "Settings", "Model Providers");

    const list = page.getByTestId("provider-list");
    const items = list.locator("[data-testid^='provider-item-']");
    await expect(items.first()).toBeVisible();
    const lastItem = items.last();

    const listBox = await list.boundingBox();
    if (!listBox) throw new Error("The provider list has no layout box");
    await page.mouse.move(listBox.x + listBox.width / 2, listBox.y + 40);
    await page.mouse.wheel(0, 2000);

    await expect(lastItem).toBeInViewport({ ratio: 1 });
    // A parent that hides its overflow can cut the item off while it is still inside the window.
    const clipped = await lastItem.evaluate((item) => {
      const itemBottom = item.getBoundingClientRect().bottom;
      for (let box = item.parentElement; box; box = box.parentElement) {
        if (getComputedStyle(box).overflowY === "visible") continue;
        if (itemBottom > box.getBoundingClientRect().bottom + 1) return true;
      }
      return false;
    });
    expect(clipped).toBe(false);
  },
);
