import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

const PERMISSIONS_ROUTE = "**/api/v1/authz/me/permissions";
const NODE_SELECTOR = '[data-testid^="rf__node-"]';

// The add path is gated on the flow permission query, which fails closed while
// it resolves. The regression this guards is not the gate but the affordance:
// the control used to stay enabled for that window, so the click was accepted
// by the UI and then discarded with no toast, no cursor change and no request.
// Holding the response open makes the window deterministic instead of racing
// a round trip that is only milliseconds wide on localhost.
test(
  "add component control refuses the click while the permission check is pending",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    let permissionRequests = 0;
    let releasePermissions: () => void = () => {};
    const permissionsHeld = new Promise<void>((resolve) => {
      releasePermissions = resolve;
    });

    // Installed only after the home page settles, so the held request is the
    // flow editor's own provider and not the one behind the flow list.
    await page.route(PERMISSIONS_ROUTE, async (route) => {
      permissionRequests += 1;
      await permissionsHeld;
      await route.continue();
    });

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 30000,
    });

    const addButton = page.getByTestId("sidebar-custom-component-button");
    await expect(addButton).toBeVisible({ timeout: 30000 });

    // Without this the whole test would pass vacuously on any build where the
    // editor stops querying permissions: there would be no pending window to
    // assert about and every assertion below would hold for the wrong reason.
    // Polled rather than read once: the counter is incremented by the route
    // handler on the Node side, which has no ordering guarantee against the
    // browser-side visibility this assertion follows.
    await expect
      .poll(() => permissionRequests, { timeout: 30000 })
      .toBeGreaterThan(0);

    await expect(addButton).toBeDisabled();
    await expect(page.locator(NODE_SELECTOR)).toHaveCount(0);

    releasePermissions();

    // The same single click on the same control, once the answer has arrived.
    await expect(addButton).toBeEnabled({ timeout: 30000 });
    await addButton.click();
    await expect(page.locator(NODE_SELECTOR)).toHaveCount(1, {
      timeout: 30000,
    });
  },
);
