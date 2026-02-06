import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

function isJsonPatchRequest(request: any): boolean {
  return (
    request.method() === "PATCH" &&
    request.url().includes("/api/v1/flows/") &&
    request.url().includes("/json-patch")
  );
}

function isJsonPatchResponse(response: any): boolean {
  return isJsonPatchRequest(response.request());
}

// Helper to set up request/response capture for JSON Patch
function setupPatchCapture(page: any) {
  let capturedPayloads: any[] = [];
  let failedResponses: any[] = [];

  page.on("request", (request: any) => {
    if (isJsonPatchRequest(request)) {
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

  page.on("response", (response: any) => {
    if (isJsonPatchResponse(response) && response.status() >= 400) {
      failedResponses.push({
        status: response.status(),
        url: response.url(),
      });
    }
  });

  return {
    getLatest: () => capturedPayloads[capturedPayloads.length - 1],
    getAll: () => capturedPayloads,
    getFailures: () => failedResponses,
    clear: () => {
      capturedPayloads = [];
      failedResponses = [];
    },
  };
}

// Helper to wait for a JSON Patch save to complete (request + successful response)
async function waitForPatchSave(page: any) {
  const response = await page.waitForResponse(
    (r: any) => isJsonPatchResponse(r) && r.status() === 200,
    { timeout: 15000 },
  );
  return response;
}

// Helper to wait for flow to load with proper timeouts
async function waitForFlowToLoad(page: any) {
  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 30000,
  });
  await page.waitForSelector(".react-flow__node", { timeout: 30000 });
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
      const initialNodeCount = await page.locator(".react-flow__node").count();
      console.log(`Found ${initialNodeCount} nodes on canvas`);
      expect(initialNodeCount).toBeGreaterThanOrEqual(3);

      // Click on the first node to select it
      await page.locator(".react-flow__node").first().click({ timeout: 5000 });
      await page.waitForTimeout(500);

      // Delete the node and wait for auto-save to complete
      await page.keyboard.press("Delete");
      await waitForPatchSave(page);

      // Verify no failed responses
      expect(patchCapture.getFailures()).toHaveLength(0);

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

        // Delete the edge and wait for auto-save
        await page.keyboard.press("Delete");
        await waitForPatchSave(page);

        // Verify no failed responses
        expect(patchCapture.getFailures()).toHaveLength(0);

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

  test(
    "should maintain correct UI state after multiple sequential saves",
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

      const initialNodeCount = await page.locator(".react-flow__node").count();
      console.log(`Initial node count: ${initialNodeCount}`);
      expect(initialNodeCount).toBeGreaterThanOrEqual(3);

      // === First deletion ===
      const firstNodeToDelete = page.locator(".react-flow__node").last();
      await firstNodeToDelete.click({ timeout: 5000 });
      await page.waitForTimeout(500);

      // Delete and wait for the save to succeed
      await page.keyboard.press("Delete");
      console.log("Deleted first node");
      await waitForPatchSave(page);

      // Verify first deletion in UI
      const countAfterFirstDelete = await page
        .locator(".react-flow__node")
        .count();
      expect(countAfterFirstDelete).toBe(initialNodeCount - 1);
      console.log(`Node count after first delete: ${countAfterFirstDelete}`);

      // Verify patch was sent successfully
      expect(patchCapture.getFailures()).toHaveLength(0);
      const firstPayload = patchCapture.getLatest();
      expect(firstPayload).not.toBeNull();
      expect(
        firstPayload.operations.some((op: any) => op.op === "remove"),
      ).toBe(true);

      // === Second deletion ===
      patchCapture.clear();

      const secondNodeToDelete = page.locator(".react-flow__node").last();
      await secondNodeToDelete.click({ timeout: 5000 });
      await page.waitForTimeout(500);

      // Delete and wait for the save to succeed
      await page.keyboard.press("Delete");
      console.log("Deleted second node");
      await waitForPatchSave(page);

      // Verify second deletion in UI
      const countAfterSecondDelete = await page
        .locator(".react-flow__node")
        .count();
      expect(countAfterSecondDelete).toBe(initialNodeCount - 2);
      console.log(`Node count after second delete: ${countAfterSecondDelete}`);

      // Verify second patch was sent successfully
      expect(patchCapture.getFailures()).toHaveLength(0);
      const secondPayload = patchCapture.getLatest();
      expect(secondPayload).not.toBeNull();
      expect(
        secondPayload.operations.some((op: any) => op.op === "remove"),
      ).toBe(true);

      // === Verify persistence by reloading ===
      await page.reload();
      await waitForFlowToLoad(page);

      const countAfterReload = await page.locator(".react-flow__node").count();
      expect(countAfterReload).toBe(initialNodeCount - 2);
      console.log(`Node count after reload: ${countAfterReload}`);

      console.log(
        `✓ Test passed: UI state consistent after multiple saves (${initialNodeCount} → ${countAfterReload} nodes)`,
      );
    },
  );
});
