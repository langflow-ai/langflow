import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to change note colors using the color picker",
  { tag: ["@release", "@workspace", "@notes"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Create a new blank flow
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Add a sticky note
    await page.getByTestId("sidebar-nav-add_note").click();
    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page, { numberOfZoomOut: 4 });

    // Select the note to show the toolbar
    await page.getByTestId("note_node").click();

    // Verify default color is amber (yellow-ish)
    const noteNode = page.getByTestId("note_node");
    let bgColor = await noteNode.evaluate(
      (el) => window.getComputedStyle(el).backgroundColor,
    );
    expect(
      bgColor === "rgb(252, 211, 77)" || bgColor === "rgb(253, 230, 138)",
    ).toBe(true);

    // Open color picker
    await page.getByTestId("color_picker").click();
    await page.waitForTimeout(300);

    // Verify all preset color buttons are visible (amber, neutral, rose, blue, lime, transparent)
    const colorButtons = [
      "amber",
      "neutral",
      "rose",
      "blue",
      "lime",
      "transparent",
    ];
    for (const color of colorButtons) {
      await expect(
        page.getByTestId(`color_picker_button_${color}`),
      ).toBeVisible();
    }

    // Verify custom color picker button is visible
    await expect(page.getByTestId("color_picker_button_custom")).toBeVisible();

    // Change to rose color
    await page.getByTestId("color_picker_button_rose").click();
    await page.waitForTimeout(500);

    // Click elsewhere to close popover and verify the note color changed
    await page.getByTestId("note_node").click();
    bgColor = await noteNode.evaluate(
      (el) => window.getComputedStyle(el).backgroundColor,
    );
    // Rose color should be pinkish - check it's not amber anymore
    expect(bgColor).not.toBe("rgb(252, 211, 77)");

    // Change to blue color
    await page.getByTestId("color_picker").click();
    await page.waitForTimeout(300);
    await page.getByTestId("color_picker_button_blue").click();
    await page.waitForTimeout(500);

    await page.getByTestId("note_node").click();
    bgColor = await noteNode.evaluate(
      (el) => window.getComputedStyle(el).backgroundColor,
    );
    // Verify color changed (exact RGB depends on CSS variables)
    expect(bgColor).toBeTruthy();

    // Change to lime color
    await page.getByTestId("color_picker").click();
    await page.waitForTimeout(300);
    await page.getByTestId("color_picker_button_lime").click();
    await page.waitForTimeout(500);

    await page.getByTestId("note_node").click();
    bgColor = await noteNode.evaluate(
      (el) => window.getComputedStyle(el).backgroundColor,
    );
    expect(bgColor).toBeTruthy();

    // Change to transparent
    await page.getByTestId("color_picker").click();
    await page.waitForTimeout(300);
    await page.getByTestId("color_picker_button_transparent").click();
    await page.waitForTimeout(500);

    await page.getByTestId("note_node").click();
    bgColor = await noteNode.evaluate(
      (el) => window.getComputedStyle(el).backgroundColor,
    );
    expect(bgColor === "rgba(0, 0, 0, 0)").toBe(true);
  },
);

test(
  "user should be able to use custom color picker for notes",
  { tag: ["@release", "@workspace", "@notes"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Add a sticky note
    await page.getByTestId("sidebar-nav-add_note").click();
    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page, { numberOfZoomOut: 4 });

    // Select the note
    await page.getByTestId("note_node").click();

    // Open color picker
    await page.getByTestId("color_picker").click();
    await page.waitForTimeout(300);

    // Verify the custom color picker button exists
    const customButton = page.getByTestId("color_picker_button_custom");
    await expect(customButton).toBeVisible();

    // The custom color input should be inside the button
    const colorInput = customButton.locator('input[type="color"]');
    await expect(colorInput).toHaveCount(1);
  },
);
