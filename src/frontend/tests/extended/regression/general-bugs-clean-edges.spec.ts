import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "custom component outputs should persist connections after page refresh",
  { tag: ["@release", "@components"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    // Create custom component with 6 outputs
    await page.getByTestId("sidebar-custom-component-button").click();

    await expect(page.getByTestId("code-button-modal")).toBeVisible({
      timeout: 3000,
    });

    await page.getByTestId("code-button-modal").last().click();

    const customComponentCode = `
from langflow.custom import Component
from langflow.io import Output
from langflow.schema.message import Message

class CustomComponent(Component):
    display_name = "Custom Component"
    description = "Test component with multiple outputs"
    icon = "custom_components"
    name = "CustomComponent"

    outputs = [
        Output(display_name="Test 1", name="test_1", method="hello_world", group_outputs=True),
        Output(display_name="Test 2", name="test_2", method="hello_world", group_outputs=True),
        Output(display_name="Test 3", name="test_3", method="hello_world", group_outputs=False),
        Output(display_name="Test 4", name="test_4", method="hello_world", group_outputs=False),
        Output(display_name="Test 5", name="test_5", method="hello_world"),
        Output(display_name="Test 6", name="test_6", method="hello_world"),
    ]

    def hello_world(self) -> Message:
        return Message(text="Hello, World!")
`;

    await page.locator(".ace_content").click();
    await page.keyboard.press(`ControlOrMeta+A`);
    await page.locator("textarea").fill(customComponentCode);

    await page.getByText("Check & Save").last().click();

    await page.waitForTimeout(1000);

    // Verify first two outputs appear separately
    await expect(
      page.getByTestId("handle-customcomponent-shownode-test 1-right"),
    ).toBeVisible();
    await expect(
      page.getByTestId("handle-customcomponent-shownode-test 2-right"),
    ).toBeVisible();

    // Verify the rest appear as a dropdown
    // Find the dropdown trigger by looking for "Test 3" with ChevronDown sibling
    const test3Element = page.locator('text="Test 3"');
    await expect(test3Element).toBeVisible();

    const dropdownTrigger = test3Element
      .locator("..", { has: page.locator('[data-testid="icon-ChevronDown"]') })
      .locator('[data-testid="icon-ChevronDown"]');
    await expect(dropdownTrigger).toBeVisible();

    // Click the dropdown to expand it
    await dropdownTrigger.click();

    // Verify dropdown items appear
    await expect(
      page.getByTestId("dropdown-item-output-undefined-test 3"),
    ).toBeVisible();
    await expect(
      page.getByTestId("dropdown-item-output-undefined-test 4"),
    ).toBeVisible();
    await expect(
      page.getByTestId("dropdown-item-output-undefined-test 5"),
    ).toBeVisible();
    await expect(
      page.getByTestId("dropdown-item-output-undefined-test 6"),
    ).toBeVisible();

    // Close the dropdown
    await dropdownTrigger.click();

    // Add 3 Chat Output components
    for (let i = 0; i < 3; i++) {
      await page.getByTestId("sidebar-search-input").click();
      await page.getByTestId("sidebar-search-input").fill("chat output");
      await page.waitForSelector('[data-testid="input_outputChat Output"]', {
        timeout: 100000,
      });

      await page
        .getByTestId("input_outputChat Output")
        .dragTo(page.locator('//*[@id="react-flow-id"]'), {
          targetPosition: { x: 800, y: 100 + i * 100 },
        });

      await page.getByTestId("sidebar-search-input").clear();
    }

    await page.waitForTimeout(1000);

    // Connect Test 1 and Test 2 outputs (separate outputs)
    await page
      .getByTestId("handle-customcomponent-shownode-test 1-right")
      .click();
    await page
      .locator('[data-testid="handle-chatoutput-noshownode-inputs-target"]')
      .first()
      .click();

    await page
      .getByTestId("handle-customcomponent-shownode-test 2-right")
      .click();
    await page
      .locator('[data-testid="handle-chatoutput-noshownode-inputs-target"]')
      .nth(1)
      .click();

    // Connect Test 3 from dropdown
    await dropdownTrigger.click();
    await page.getByTestId("dropdown-item-output-undefined-test 3").click();

    await page.waitForTimeout(500);

    // Now use the handle that appears for Test 3
    await page
      .getByTestId("handle-customcomponent-shownode-test 3-right")
      .click();
    await page
      .locator('[data-testid="handle-chatoutput-noshownode-inputs-target"]')
      .nth(2)
      .click();

    await page.waitForTimeout(500);

    // Verify we have 3 edges connected
    let edgeCount = await page.locator(".react-flow__edge").count();
    expect(edgeCount).toBe(3);

    // Change dropdown option to Test 4 and verify edge disappeared
    await dropdownTrigger.click();
    await page.getByTestId("dropdown-item-output-undefined-test 4").click();

    await page.waitForTimeout(500);

    edgeCount = await page.locator(".react-flow__edge").count();
    expect(edgeCount).toBe(2);

    // Change back to Test 3 and verify edge is still missing (doesn't come back)
    // Now the dropdown is showing Test 4, so re-query for it
    const test4Element = page.locator('text="Test 4"');
    const dropdownTrigger4 = test4Element
      .locator("..", { has: page.locator('[data-testid="icon-ChevronDown"]') })
      .locator('[data-testid="icon-ChevronDown"]');

    await dropdownTrigger4.click();
    await page.getByTestId("dropdown-item-output-undefined-test 3").click();

    await page.waitForTimeout(500);

    edgeCount = await page.locator(".react-flow__edge").count();
    expect(edgeCount).toBe(2);

    // Change to Test 5 and connect it to the 3rd chat output
    // Now the dropdown is showing Test 3 again, so re-query for it
    const test3Element2 = page.locator('text="Test 3"');
    const dropdownTrigger3 = test3Element2
      .locator("..", { has: page.locator('[data-testid="icon-ChevronDown"]') })
      .locator('[data-testid="icon-ChevronDown"]');

    await dropdownTrigger3.click();
    await page.getByTestId("dropdown-item-output-undefined-test 5").click();

    await page.waitForTimeout(500);

    await page
      .getByTestId("handle-customcomponent-shownode-test 5-right")
      .click();
    await page
      .locator('[data-testid="handle-chatoutput-noshownode-inputs-target"]')
      .nth(2)
      .click();

    await page.waitForTimeout(2000);

    // Count edges before refresh (should have 3 edges: Test 1, Test 2, Test 5)
    const edgesBeforeRefresh = await page.locator(".react-flow__edge").count();
    expect(edgesBeforeRefresh).toBe(3);

    // Refresh the page
    await page.reload();

    await page.waitForSelector('[data-testid="div-generic-node"]', {
      timeout: 30000,
    });

    // Count edges after refresh
    const edgesAfterRefresh = await page.locator(".react-flow__edge").count();

    // Verify all edges are still connected
    expect(edgesAfterRefresh).toBe(edgesBeforeRefresh);
  },
);
