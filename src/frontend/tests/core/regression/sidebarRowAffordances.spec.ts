import { expect, test } from "../../fixtures";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

/**
 * LE-2311: the sidebar row's label wrapper is a flex item with the default
 * `min-width: auto`, so it refuses to shrink below its intrinsic content
 * width. On rows whose name (plus an optional Beta/Legacy badge) is wider
 * than the row, the sibling action container holding the add (`+`) button and
 * the drag handle is pushed past the row's right edge and clipped away.
 *
 * The row keeps working (double-click, drag, right-click), but neither
 * affordance is visible, so nothing on the row signals that it can be added
 * or dragged.
 *
 * The search term is chosen so that both a short name and several long ones
 * are on screen at once: the short row proves the measurement is sound, the
 * long ones are the regression.
 */
test(
  "sidebar add button and drag handle stay inside the row for long component names",
  { tag: ["@release", "@components", "@workspace"] },
  async ({ page }) => {
    await page.setViewportSize({ width: 1470, height: 704 });
    await openBlankFlow(page);

    await page.getByTestId("sidebar-search-input").fill("embed");
    const longRow = page.getByTestId(
      "amazon_amazon bedrock embeddings_draggable",
    );
    await expect(longRow).toBeVisible({ timeout: 30000 });

    const overflowing = await page.evaluate(() => {
      const rows = Array.from(
        document.querySelectorAll<HTMLElement>('[data-testid$="_draggable"]'),
      );
      return rows
        .map((row) => {
          const rowBox = row.getBoundingClientRect();
          const grip = row.querySelector('[data-testid="icon-GripVertical"]');
          const gripBox = grip?.getBoundingClientRect();
          return {
            name:
              row.querySelector('[data-testid="display-name"]')?.textContent ??
              row.getAttribute("data-testid"),
            // Positive means the handle sticks out past the row's right edge.
            overflow: gripBox ? Math.round(gripBox.right - rowBox.right) : null,
          };
        })
        .filter((r) => r.overflow === null || r.overflow > 0);
    });

    expect(
      overflowing,
      `rows whose drag handle renders outside the row: ${JSON.stringify(
        overflowing,
      )}`,
    ).toEqual([]);

    // The `+` is hidden until hover by design; on an affected row it never
    // appears at all because the whole action container is off the row.
    await longRow.hover();

    const addButton = longRow.getByTestId(
      "add-component-button-amazon-bedrock-embeddings",
    );
    await expect(addButton).toBeVisible();

    const rowBox = await longRow.boundingBox();
    const addBox = await addButton.boundingBox();
    expect(rowBox).not.toBeNull();
    expect(addBox).not.toBeNull();
    expect(addBox!.x + addBox!.width).toBeLessThanOrEqual(
      rowBox!.x + rowBox!.width,
    );

    await addButton.click();
    await expect(page.locator(".react-flow__node")).toHaveCount(1);
  },
);
