import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { routeTestScopedDefaultFlowNames } from "../../utils/flow/route-test-scoped-default-flow-names";

test.beforeEach(async ({ page }, testInfo) => {
  await routeTestScopedDefaultFlowNames(page, testInfo, "note-color");
});

test(
  "user should be able to change note colors using the color picker",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Create a new blank flow
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Add a sticky note
    await page.getByTestId("canvas-add-note-button").click();
    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();
    await adjustScreenView(page, { numberOfZoomOut: 4 });

    // Select the note to show the toolbar
    await page.getByTestId("note_node").click();

    // Verify default color is amber (yellow-ish)
    const noteNode = page.getByTestId("note_node");
    const readNoteColor = () =>
      noteNode.evaluate((el) => window.getComputedStyle(el).backgroundColor);
    let bgColor = await readNoteColor();
    expect(
      bgColor === "rgb(252, 211, 77)" || bgColor === "rgb(253, 230, 138)",
    ).toBe(true);

    // Open color picker
    await page.getByTestId("color_picker").click();

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
    const amberColor = bgColor;
    await page.getByTestId("color_picker_button_rose").click();

    // Click elsewhere to close popover and verify the note color changed
    await page.getByTestId("note_node").click();
    await expect.poll(readNoteColor).not.toBe(amberColor);
    bgColor = await readNoteColor();
    // Rose color should be pinkish - check it's not amber anymore
    expect(bgColor).not.toBe("rgb(252, 211, 77)");

    // Change to blue color
    await page.getByTestId("color_picker").click();
    const blueButton = page.getByTestId("color_picker_button_blue");
    await expect(blueButton).toBeVisible();
    const roseColor = bgColor;
    await blueButton.click();

    await page.getByTestId("note_node").click();
    await expect.poll(readNoteColor).not.toBe(roseColor);
    bgColor = await readNoteColor();
    // Verify color changed (exact RGB depends on CSS variables)
    expect(bgColor).toBeTruthy();

    // Change to lime color
    await page.getByTestId("color_picker").click();
    const limeButton = page.getByTestId("color_picker_button_lime");
    await expect(limeButton).toBeVisible();
    const blueColor = bgColor;
    await limeButton.click();

    await page.getByTestId("note_node").click();
    await expect.poll(readNoteColor).not.toBe(blueColor);
    bgColor = await readNoteColor();
    expect(bgColor).toBeTruthy();

    // Change to transparent
    await page.getByTestId("color_picker").click();
    const transparentButton = page.getByTestId(
      "color_picker_button_transparent",
    );
    await expect(transparentButton).toBeVisible();
    await transparentButton.click();

    await page.getByTestId("note_node").click();
    await expect.poll(readNoteColor).toBe("rgba(0, 0, 0, 0)");
    bgColor = await readNoteColor();
    expect(bgColor === "rgba(0, 0, 0, 0)").toBe(true);
  },
);

test(
  "user should be able to use custom color picker for notes",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Add a sticky note
    await page.getByTestId("canvas-add-note-button").click();
    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();
    await adjustScreenView(page, { numberOfZoomOut: 4 });

    // Select the note
    await page.getByTestId("note_node").click();

    // Open color picker
    await page.getByTestId("color_picker").click();

    // Verify the custom color picker button exists
    const customButton = page.getByTestId("color_picker_button_custom");
    await expect(customButton).toBeVisible();

    // The custom color input should be inside the button
    const colorInput = customButton.locator('input[type="color"]');
    await expect(colorInput).toHaveCount(1);
  },
);
