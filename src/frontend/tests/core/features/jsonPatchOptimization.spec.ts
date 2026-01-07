import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// Helper to set up request capture for JSON Patch
function setupPatchCapture(page: any) {
  let capturedPayloads: any[] = [];

  page.on("request", (request: any) => {
    const url = request.url();
    if (
      request.method() === "PATCH" &&
      url.includes("/api/v1/flows/") &&
      url.includes("/json-patch")
    ) {
      try {
        const postData = request.postData();
        if (postData) {
          capturedPayloads.push(JSON.parse(postData));
        }
      } catch (e) {
        console.error("Failed to parse request payload:", e);
      }
    }
  });

  return {
    getLatest: () => capturedPayloads[capturedPayloads.length - 1],
    getAll: () => capturedPayloads,
    clear: () => {
      capturedPayloads = [];
    },
  };
}

// Helper to wait for flow to load with proper timeouts
async function waitForFlowToLoad(page: any) {
  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 30000,
  });
  await page.waitForSelector("[data-id]", { timeout: 30000 });
  // Wait for initial auto-save to complete
  await page.waitForTimeout(2000);
}

test.describe("JSON Patch Optimization", () => {
  test(
    "should generate minimal JSON Patch operations when removing a node",
    { tag: ["@release", "@optimization"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      // Open a starter flow with multiple nodes
      await page
        .getByTestId("side_nav_options_all-templates")
        .click({ timeout: 5000 });
      await page
        .getByRole("heading", { name: "Basic Prompting" })
        .click({ timeout: 10000, force: true });

      await waitForFlowToLoad(page);

      const patchCapture = setupPatchCapture(page);

      // Get all nodes on the canvas
      const nodes = await page.locator("[data-id]").all();
      console.log(`Found ${nodes.length} nodes on canvas`);
      expect(nodes.length).toBeGreaterThanOrEqual(3);

      // Click on the first node to select it
      await nodes[0].click({ timeout: 5000 });
      await page.waitForTimeout(500);

      // Delete the node
      await page.keyboard.press("Delete");

      // Wait for auto-save
      await page.waitForTimeout(3000);

      // Validate the captured request payload
      const payload = patchCapture.getLatest();
      expect(payload).not.toBeNull();
      expect(payload.operations).toBeDefined();
      expect(Array.isArray(payload.operations)).toBe(true);

      console.log("Operations captured:");
      payload.operations.forEach((op: any, idx: number) => {
        console.log(`  ${idx + 1}. ${op.op} at ${op.path}`);
      });

      // Should be minimal operations for node deletion
      expect(payload.operations.length).toBeLessThanOrEqual(10);

      // Should have at least one remove operation
      const hasRemoveOperation = payload.operations.some(
        (op: any) => op.op === "remove",
      );
      expect(hasRemoveOperation).toBe(true);

      // Verify RFC 6902 format
      payload.operations.forEach((op: any) => {
        expect(op).toHaveProperty("op");
        expect(op).toHaveProperty("path");
        expect(["add", "remove", "replace", "move", "copy", "test"]).toContain(
          op.op,
        );
      });

      console.log(
        `✓ Test passed: Generated ${payload.operations.length} operations (expected ≤10)`,
      );
    },
  );

  test(
    "should handle edge operations efficiently",
    { tag: ["@release", "@optimization"] },
    async ({ page }) => {
      await awaitBootstrapTest(page);

      await page
        .getByTestId("side_nav_options_all-templates")
        .click({ timeout: 5000 });
      await page
        .getByRole("heading", { name: "Basic Prompting" })
        .click({ timeout: 10000, force: true });

      await waitForFlowToLoad(page);

      const patchCapture = setupPatchCapture(page);

      // Get initial edge count
      const initialEdges = await page.locator(".react-flow__edge").all();
      console.log(`Initial edge count: ${initialEdges.length}`);

      if (initialEdges.length > 0) {
        // Click on an edge to select it
        await initialEdges[0].click({ timeout: 5000 });
        await page.waitForTimeout(500);

        // Delete the edge
        await page.keyboard.press("Delete");

        // Wait for auto-save
        await page.waitForTimeout(3000);

        // Verify edge was removed
        const afterDeleteEdges = await page.locator(".react-flow__edge").all();
        expect(afterDeleteEdges.length).toBe(initialEdges.length - 1);

        // Verify patch was captured
        const payload = patchCapture.getLatest();
        expect(payload).not.toBeNull();
        expect(payload.operations).toBeDefined();

        console.log("Operations captured for edge delete:");
        payload.operations.forEach((op: any, idx: number) => {
          console.log(`  ${idx + 1}. ${op.op} at ${op.path}`);
        });

        // Should have remove operation targeting edges
        const hasEdgeRemove = payload.operations.some(
          (op: any) => op.op === "remove" && op.path.includes("/data/edges"),
        );
        expect(hasEdgeRemove).toBe(true);

        // Edge removal should be minimal operations
        expect(payload.operations.length).toBeLessThanOrEqual(5);

        console.log(
          `✓ Test passed: Edge delete generated ${payload.operations.length} operations`,
        );
      } else {
        console.log("⚠ Skipped: No edges found to delete");
      }
    },
  );
});
