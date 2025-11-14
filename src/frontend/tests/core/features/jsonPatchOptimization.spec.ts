import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test.describe("JSON Patch Optimization", () => {
  test(
    "should generate minimal JSON Patch operations when removing a node",
    { tag: ["@release", "@optimization"] },
    async ({ page }) => {
      // Navigate to Langflow and bootstrap
      await awaitBootstrapTest(page);

      // Open a starter flow with multiple nodes (Basic Prompting has 3+ nodes)
      await page.getByTestId("side_nav_options_all-templates").click();
      await page.getByRole("heading", { name: "Basic Prompting" }).click();

      // Wait for the flow to load completely
      await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
        timeout: 100000,
      });

      // Wait for nodes to be rendered on canvas
      await page.waitForSelector("[data-id]", { timeout: 10000 });

      // Give it a moment to ensure auto-save has completed initial save
      await page.waitForTimeout(2000);

      // Set up network request interception to capture PATCH requests
      let capturedRequest: any = null;
      let capturedPayload: any = null;

      page.on("request", (request) => {
        const url = request.url();
        // Capture PATCH requests to the json-patch endpoint
        if (
          request.method() === "PATCH" &&
          url.includes("/api/v1/flows/") &&
          url.includes("/json-patch")
        ) {
          capturedRequest = request;
          try {
            const postData = request.postData();
            if (postData) {
              capturedPayload = JSON.parse(postData);
              console.log("Captured JSON Patch payload:", capturedPayload);
              console.log(
                "Number of operations:",
                capturedPayload.operations?.length || 0,
              );
            }
          } catch (e) {
            console.error("Failed to parse request payload:", e);
          }
        }
      });

      // Get all nodes on the canvas
      const nodes = await page.locator("[data-id]").all();
      console.log(`Found ${nodes.length} nodes on canvas`);

      // Ensure we have at least 3 nodes to work with
      expect(nodes.length).toBeGreaterThanOrEqual(3);

      // Click on the first node to select it
      await nodes[0].click();

      // Wait for the node to be selected
      await page.waitForTimeout(500);

      // Delete the node using the Delete key
      await page.keyboard.press("Delete");

      // Wait for the auto-save to trigger (the PATCH request should happen)
      await page.waitForTimeout(3000);

      // Validate the captured request payload
      expect(capturedRequest).not.toBeNull();
      expect(capturedPayload).not.toBeNull();
      expect(capturedPayload.operations).toBeDefined();
      expect(Array.isArray(capturedPayload.operations)).toBe(true);

      // Log the operations for debugging
      console.log("Operations captured:");
      capturedPayload.operations.forEach((op: any, idx: number) => {
        console.log(`  ${idx + 1}. ${op.op} at ${op.path}`);
      });

      // Assert that operations.length is less than 10
      // (should be ~2-5 for a simple node deletion with ID-aware diffing)
      expect(capturedPayload.operations.length).toBeLessThanOrEqual(10);

      // Assert that operations include at least one remove operation
      const hasRemoveOperation = capturedPayload.operations.some(
        (op: any) => op.op === "remove",
      );
      expect(hasRemoveOperation).toBe(true);

      // Verify the operations follow RFC 6902 JSON Patch format
      capturedPayload.operations.forEach((op: any) => {
        expect(op).toHaveProperty("op");
        expect(op).toHaveProperty("path");
        expect(["add", "remove", "replace", "move", "copy", "test"]).toContain(
          op.op,
        );
      });

      console.log(
        `✓ Test passed: Generated ${capturedPayload.operations.length} operations (expected ≤10)`,
      );
    },
  );
});
