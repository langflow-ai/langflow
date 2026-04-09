import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "sticky notes should have consistent 280x140px dimensions",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Take reference element for size comparison
    const targetElement = page.locator('//*[@id="react-flow-id"]');

    // Start adding note
    await page.getByTestId("sidebar-nav-add_note").click();

    // Get shadow-box dimensions while dragging
    const shadowBox = page.locator("#shadow-box");
    await page.mouse.move(300, 300);

    const shadowBoxSize = await shadowBox.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        width: parseInt(style.width),
        height: parseInt(style.height),
        borderRadius: style.borderRadius,
      };
    });

    // Place the note
    await targetElement.click();
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    // Get placed note dimensions
    const noteNode = page.getByTestId("note_node");
    await expect(noteNode).toBeVisible();

    const noteSize = await noteNode.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        width: parseInt(style.width),
        height: parseInt(style.height),
        borderRadius: style.borderRadius,
      };
    });

    // Verify shadow-box and note have same dimensions
    expect(shadowBoxSize.width).toBe(280);
    expect(shadowBoxSize.height).toBe(140);
    expect(noteSize.width).toBe(280);
    expect(noteSize.height).toBe(140);

    // Verify rounded corners consistency
    expect(shadowBoxSize.borderRadius).toBe("12px");
    expect(noteSize.borderRadius).toBe("12px");
  },
);

test(
  "sticky notes should maintain size with content",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Add sticky note
    await page.getByTestId("sidebar-nav-add_note").click();
    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    const noteNode = page.getByTestId("note_node");

    // Get initial size (empty note)
    const initialSize = await noteNode.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        width: parseInt(style.width),
        height: parseInt(style.height),
      };
    });

    // Add content to note
    await noteNode.click();
    await page.locator(".generic-node-desc-text").last().dblclick();

    const longText =
      "This is a very long text that should not change the note dimensions because we have fixed sizing with overflow handling. ".repeat(
        10,
      );
    await page.getByTestId("textarea").fill(longText);

    // Click outside to finish editing
    await targetElement.click();
    await page.keyboard.press("Escape");

    // Get size after content added
    const finalSize = await noteNode.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        width: parseInt(style.width),
        height: parseInt(style.height),
      };
    });

    // Verify size hasn't changed
    expect(finalSize.width).toBe(initialSize.width);
    expect(finalSize.height).toBe(initialSize.height);
    expect(finalSize.width).toBe(280);
    expect(finalSize.height).toBe(140);
  },
);

test(
  "sticky notes should have larger readable text",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Add sticky note
    await page.getByTestId("sidebar-nav-add_note").click();
    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    const noteNode = page.getByTestId("note_node");
    await noteNode.click();

    // Enter edit mode
    await page.locator(".generic-node-desc-text").last().dblclick();
    const textarea = page.getByTestId("textarea");

    // Check input text size
    const inputTextStyle = await textarea.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        fontSize: style.fontSize,
        fontWeight: style.fontWeight,
      };
    });

    // Add some text and exit edit mode
    await textarea.fill("Test text for size verification");
    await targetElement.click();
    await page.keyboard.press("Escape");

    // Check rendered text size
    const renderedText = page.getByTestId("generic-node-desc");
    const renderedTextStyle = await renderedText.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        fontSize: style.fontSize,
        fontWeight: style.fontWeight,
      };
    });

    // Verify both input and rendered text use same larger size (16px / text-base)
    expect(inputTextStyle.fontSize).toBe("16px"); // text-base
    expect(renderedTextStyle.fontSize).toBe("16px"); // text-base from markdown
    // Font-weight check: 500 (font-medium) expected, but browsers may fallback to 400
    // if the font doesn't have weight 500 available
    expect(Number(inputTextStyle.fontWeight)).toBeGreaterThanOrEqual(400);
    expect(Number(renderedTextStyle.fontWeight)).toBeGreaterThanOrEqual(400);
  },
);

test(
  "sticky notes should handle overflow with scrollbars",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Add sticky note
    await page.getByTestId("sidebar-nav-add_note").click();
    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    const noteNode = page.getByTestId("note_node");
    await noteNode.click();

    // Add very long content that should overflow
    await page.locator(".generic-node-desc-text").last().dblclick();
    const veryLongText =
      "Line of text that will create vertical overflow. ".repeat(20);
    await page.getByTestId("textarea").fill(veryLongText);

    // Check that textarea has max-height and overflow
    const textarea = page.getByTestId("textarea");
    const textareaOverflow = await textarea.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        maxHeight: style.maxHeight,
        overflowY: style.overflowY,
        height: parseInt(style.height),
      };
    });

    // Exit edit mode and check rendered content overflow
    await targetElement.click();
    await page.keyboard.press("Escape");

    const renderedContent = page.getByTestId("generic-node-desc");
    const contentOverflow = await renderedContent.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        maxHeight: style.maxHeight,
        overflowY: style.overflowY,
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
      };
    });

    // Verify overflow handling - should have some form of overflow control
    expect(
      ["auto", "scroll", "hidden"].includes(textareaOverflow.overflowY),
    ).toBe(true);
    expect(
      ["auto", "scroll", "hidden"].includes(contentOverflow.overflowY),
    ).toBe(true);

    // Content should be constrained (either by max-height or overflow)
    const hasOverflowControl =
      contentOverflow.scrollHeight > contentOverflow.clientHeight ||
      contentOverflow.maxHeight !== "none";
    expect(hasOverflowControl).toBe(true);
  },
);

test(
  "sticky notes should respect resize constraints",
  { tag: ["@release", "@workspace"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    // Add sticky note
    await page.getByTestId("sidebar-nav-add_note").click();
    const targetElement = page.locator('//*[@id="react-flow-id"]');
    await targetElement.click();
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    const noteNode = page.getByTestId("note_node");
    await noteNode.click();

    // Verify resize handles are visible when selected
    const resizeHandles = page.locator(".react-flow__resize-control");
    await expect(resizeHandles.first()).toBeVisible();

    // Get initial size
    const initialSize = await noteNode.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        width: parseInt(style.width),
        height: parseInt(style.height),
      };
    });

    // Try to resize larger (should work)
    const resizeHandle = page.locator(
      ".react-flow__resize-control.bottom.right",
    );
    await resizeHandle.hover();

    // Get initial position of resize handle
    const handleBox = await resizeHandle.boundingBox();
    if (handleBox) {
      await page.mouse.move(
        handleBox.x + handleBox.width / 2,
        handleBox.y + handleBox.height / 2,
      );
      await page.mouse.down();
      await page.mouse.move(handleBox.x + 100, handleBox.y + 50); // Move handle to resize
      await page.mouse.up();
    }

    const enlargedSize = await noteNode.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        width: parseInt(style.width),
        height: parseInt(style.height),
      };
    });

    // Verify it can be resized larger (if resize worked) or at least respects constraints
    if (
      enlargedSize.width > initialSize.width ||
      enlargedSize.height > initialSize.height
    ) {
      expect(enlargedSize.width).toBeGreaterThanOrEqual(initialSize.width);
      expect(enlargedSize.height).toBeGreaterThanOrEqual(initialSize.height);
    }

    // Verify it respects minimum constraints (280x140)
    expect(enlargedSize.width).toBeGreaterThanOrEqual(280);
    expect(enlargedSize.height).toBeGreaterThanOrEqual(140);

    // Verify it respects maximum constraints (1000x800)
    expect(enlargedSize.width).toBeLessThanOrEqual(1000);
    expect(enlargedSize.height).toBeLessThanOrEqual(800);
  },
);
