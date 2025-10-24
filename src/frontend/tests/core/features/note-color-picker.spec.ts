import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to select colors using both preset buttons and native color picker",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Create a blank flow
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Add a note node
    await page.getByTestId("sidebar-nav-add_note").click();
    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page, { numberOfZoomOut: 6 });

    // Click on the note node
    await page.getByTestId("note_node").click();

    // TEST 1: Verify preset color buttons are visible
    await page.getByTestId("color_picker").click();

    // Check that all preset color buttons exist
    await expect(page.getByTestId("color_picker_button_amber")).toBeVisible();
    await expect(page.getByTestId("color_picker_button_neutral")).toBeVisible();
    await expect(page.getByTestId("color_picker_button_rose")).toBeVisible();
    await expect(page.getByTestId("color_picker_button_blue")).toBeVisible();
    await expect(page.getByTestId("color_picker_button_lime")).toBeVisible();
    await expect(
      page.getByTestId("color_picker_button_transparent"),
    ).toBeVisible();

    // TEST 2: Verify native color picker is visible
    await expect(page.getByTestId("native_color_picker")).toBeVisible();

    // TEST 3: Test preset color selection (Rose)
    await page.getByTestId("color_picker_button_rose").click();
    await page.waitForTimeout(1000); // Wait for animation

    let element = await page.getByTestId("note_node");
    let hasRoseColor = await element?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return (
        style.backgroundColor === "rgb(253, 164, 175)" ||
        style.backgroundColor === "rgb(254, 205, 211)"
      );
    });
    expect(hasRoseColor).toBe(true);

    // TEST 4: Test preset color selection (Blue)
    await page.getByTestId("note_node").click();
    await page.getByTestId("color_picker").click();
    await page.getByTestId("color_picker_button_blue").click();
    await page.waitForTimeout(1000);

    element = await page.getByTestId("note_node");
    let hasBlueColor = await element?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return (
        style.backgroundColor === "rgb(191, 219, 254)" ||
        style.backgroundColor === "rgb(219, 234, 254)"
      );
    });
    expect(hasBlueColor).toBe(true);

    // TEST 5: Test native color picker (set custom hex color)
    await page.getByTestId("note_node").click();
    await page.getByTestId("color_picker").click();

    // Set a custom color using the native picker
    const colorInput = page.getByTestId("native_color_picker");
    await colorInput.fill("#FF5733"); // Custom orange-red color
    await page.waitForTimeout(1000);

    element = await page.getByTestId("note_node");
    let hasCustomColor = await element?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.backgroundColor === "rgb(255, 87, 51)"; // #FF5733 in RGB
    });
    expect(hasCustomColor).toBe(true);

    // TEST 6: Verify color persists after clicking away
    await targetElement.click();
    await page.getByTestId("note_node").click();

    element = await page.getByTestId("note_node");
    hasCustomColor = await element?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return style.backgroundColor === "rgb(255, 87, 51)";
    });
    expect(hasCustomColor).toBe(true);

    // TEST 7: Switch back to a preset color after using custom color
    await page.getByTestId("note_node").click();
    await page.getByTestId("color_picker").click();
    await page.getByTestId("color_picker_button_lime").click();
    await page.waitForTimeout(1000);

    element = await page.getByTestId("note_node");
    let hasLimeColor = await element?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return (
        style.backgroundColor === "rgb(217, 249, 157)" ||
        style.backgroundColor === "rgb(190, 242, 100)"
      );
    });
    expect(hasLimeColor).toBe(true);

    // TEST 8: Test transparent option
    await page.getByTestId("note_node").click();
    await page.getByTestId("color_picker").click();
    await page.getByTestId("color_picker_button_transparent").click();
    await page.waitForTimeout(1000);

    element = await page.getByTestId("note_node");
    let isTransparent = await element?.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return (
        style.backgroundColor === "rgba(0, 0, 0, 0)" ||
        style.backgroundColor === "transparent"
      );
    });
    expect(isTransparent).toBe(true);
  },
);
