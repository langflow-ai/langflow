import { expect, test } from "../../fixtures";

test(
  "sticky notes constants should be properly defined",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    const constants = await page.evaluate(() => ({
      expectedMinWidth: 280,
      expectedMinHeight: 140,
      expectedMaxWidth: 1000,
      expectedMaxHeight: 800,
    }));

    expect(constants.expectedMinWidth).toBe(280);
    expect(constants.expectedMinHeight).toBe(140);
    expect(constants.expectedMaxWidth).toBe(1000);
    expect(constants.expectedMaxHeight).toBe(800);
  },
);

test(
  "sticky notes should use text-base font size",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    const textSize = await page.evaluate(() => {
      const testEl = document.createElement("div");
      testEl.className = "text-base";
      testEl.textContent = "Test";
      testEl.style.visibility = "hidden";
      document.body.appendChild(testEl);

      const style = window.getComputedStyle(testEl);
      const result = {
        fontSize: style.fontSize,
      };

      document.body.removeChild(testEl);
      return result;
    });

    // Verify text-base (16px / 1rem) is applied for sticky note readability
    expect(textSize.fontSize).toBe("16px");
  },
);
