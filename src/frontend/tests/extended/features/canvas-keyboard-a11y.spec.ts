import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";

/**
 * WCAG 2.1.1 / 4.1.2 regression tests for canvas keyboard operation
 * (LE-1514 F1 + F3).
 *
 * - Edge creation is keyboard-operable: Enter on a source handle arms the
 *   compatibility filter, Enter on a compatible target completes the
 *   connection. This worked since #14209 gave handles Enter/Space but nothing
 *   pinned it.
 * - With disableKeyboardA11y off, arrow keys move the selected node, the move
 *   is announced through ReactFlow's aria-live region, it is undoable, and it
 *   persists — keyboard moves used to bypass both the undo snapshot and
 *   autosave, which only hung off the pointer-drag handlers.
 * - Nodes and edges expose widget roles (application / button); a tabbable
 *   "group" fails IBM element_tabbable_role_valid.
 * - Arrow keys pressed inside an open menu stay in the menu. LE-2209 (#14543)
 *   added stopCanvasKeyPropagation to the non-portaled Radix select/popover
 *   for exactly this, but it shipped while keyboard movement was still
 *   disabled — this is the first test that exercises the guard against real
 *   node movement.
 */

async function setupTwoNodeFlow(page) {
  await openBlankFlow(page);
  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    state: "visible",
  });
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill(TEXTS.searchChatOutput);
  await page.waitForSelector('[data-testid="input_outputChat Output"]', {
    timeout: 3000,
  });
  await page
    .getByTestId("input_outputChat Output")
    .hover()
    .then(async () => {
      await page.getByTestId("add-component-button-chat-output").click();
    });

  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill(TEXTS.searchChatInput);
  await page.waitForSelector('[data-testid="input_outputChat Input"]', {
    timeout: 3000,
  });
  await page
    .getByTestId("input_outputChat Input")
    .dragTo(page.locator('//*[@id="react-flow-id"]'), {
      targetPosition: { x: 100, y: 100 },
    });
  await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
    timeout: 100000,
  });
  await adjustScreenView(page);
}

test(
  "creates a connection with the keyboard alone",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await setupTwoNodeFlow(page);

    await page
      .getByTestId("handle-chatinput-noshownode-chat message-source")
      .focus();
    await page.keyboard.press("Enter");
    await page
      .getByTestId("handle-chatoutput-noshownode-inputs-target")
      .focus();
    await page.keyboard.press("Enter");

    await expect(page.locator(".react-flow__edge")).toHaveCount(1);
    // the edge lands with an accessible name and a widget role
    const edge = page.locator(".react-flow__edge").first();
    await expect(edge).toHaveAttribute("role", "button");
    await expect(edge).toHaveAttribute("aria-label", /Edge from .+ to .+/);
  },
);

test(
  "moves a node with arrow keys, announces it, and makes it undoable and persistent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await setupTwoNodeFlow(page);

    const node = page.locator(".react-flow__node").first();
    // widget role instead of the tabbable "group" ReactFlow falls back to
    await expect(node).toHaveAttribute("role", "application");
    await expect(node).toHaveAttribute("tabindex", "0");

    await node.click();
    const before = await node.evaluate((el) => el.style.transform);

    await node.focus();
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press("ArrowRight");
      await page.waitForTimeout(80);
    }
    const moved = await node.evaluate((el) => el.style.transform);
    expect(moved).not.toBe(before);

    // ReactFlow's live region (only rendered when keyboard a11y is enabled)
    // announced the move
    await expect(
      page.locator(".react-flow [aria-live='assertive']"),
    ).toContainText(/Moved selected node/);

    // undoable: one undo restores the pre-move position (the whole arrow
    // burst is a single snapshot)
    await page.keyboard.press("ControlOrMeta+z");
    await expect
      .poll(async () => node.evaluate((el) => el.style.transform))
      .toBe(before);

    // redo the move and let the debounced autosave land, then reload
    await node.click();
    await node.focus();
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press("ArrowRight");
      await page.waitForTimeout(80);
    }
    const target = await node.evaluate((el) => el.style.transform);
    await page.waitForTimeout(2500);

    await page.reload();
    await page.waitForSelector(".react-flow__node", { timeout: 30000 });
    const persisted = page.locator(".react-flow__node").first();
    await expect
      .poll(async () => persisted.evaluate((el) => el.style.transform), {
        timeout: 15000,
      })
      .toBe(target);
  },
);

test(
  "arrow keys inside an open menu never move the node underneath",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await setupTwoNodeFlow(page);

    const node = page.locator(".react-flow__node").first();
    const transform = () => node.evaluate((el) => el.style.transform);

    // toolbar more-options menu (non-portaled Radix select)
    await node.click();
    const beforeMenu = await transform();
    await page.getByTestId("more-options-modal").click();
    for (let i = 0; i < 4; i++) {
      await page.keyboard.press("ArrowDown");
      await page.waitForTimeout(60);
    }
    expect(await transform()).toBe(beforeMenu);
    await page.keyboard.press("Escape");

    // an inline field dropdown inside the second node
    const second = page.locator(".react-flow__node").nth(1);
    await second.click();
    const trigger = second.locator('[role="combobox"]').first();
    if (await trigger.count()) {
      const beforeDropdown = await second.evaluate((el) => el.style.transform);
      await trigger.click();
      for (let i = 0; i < 3; i++) {
        await page.keyboard.press("ArrowDown");
        await page.waitForTimeout(60);
      }
      expect(await second.evaluate((el) => el.style.transform)).toBe(
        beforeDropdown,
      );
      await page.keyboard.press("Escape");
    }

    // and the node is still movable once the menus are closed
    await node.click();
    await node.focus();
    await page.keyboard.press("ArrowRight");
    await expect
      .poll(async () => node.evaluate((el) => el.style.transform))
      .not.toBe(beforeMenu);
  },
);
