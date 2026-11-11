import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TIMEOUTS } from "../../utils/constants/timeouts";

const THREE_TOOLS_CODE = `from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output
from lfx.schema.message import Message


class ThreeTools(Component):
    display_name = "Three Tools"
    inputs = [MessageTextInput(name="text", display_name="Text", tool_mode=True)]
    outputs = [
        Output(display_name="First", name="first_tool", method="first_tool"),
        Output(display_name="Second", name="second_tool", method="second_tool"),
        Output(display_name="Third", name="third_tool", method="third_tool"),
    ]

    def first_tool(self) -> Message:
        return Message(text="first")

    def second_tool(self) -> Message:
        return Message(text="second")

    def third_tool(self) -> Message:
        return Message(text="third")
`;

test(
  "clicking a tool row keeps the other tools selected",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page, { skipModal: true });

    const template = await page.request.post("/api/v1/custom_component", {
      data: { code: THREE_TOOLS_CODE },
    });
    expect(template.ok()).toBeTruthy();
    const node = (await template.json()).data;
    const created = await page.request.post("/api/v1/flows/", {
      data: {
        name: `tools-row-click-${Date.now()}`,
        data: {
          nodes: [
            {
              id: "ThreeTools-a1",
              type: "genericNode",
              position: { x: 0, y: 0 },
              data: { id: "ThreeTools-a1", type: "ThreeTools", node },
            },
          ],
          edges: [],
          viewport: { x: 0, y: 0, zoom: 1 },
        },
      },
    });
    expect(created.status()).toBe(201);
    const flowId = (await created.json()).id;

    await page.goto(`/flow/${flowId}`);
    await page.getByTestId("generic-node-title-arrangement").click();
    await page.getByTestId("tool-mode-button").click();
    await page
      .getByTestId("button_open_actions")
      .click({ timeout: TIMEOUTS.standard });

    const rows = page.locator(".ag-center-cols-container .ag-row");
    const checkboxes = page.locator(
      '.ag-row [col-id="name"] input[data-ref="eInput"]',
    );
    await expect(checkboxes).toHaveCount(3, { timeout: TIMEOUTS.standard });
    for (const index of [0, 1, 2]) {
      await expect(checkboxes.nth(index)).toBeChecked();
    }

    await rows.nth(1).locator('[col-id="description"]').click();

    await expect(page.getByTestId("input_update_name")).toBeVisible();
    for (const index of [0, 1, 2]) {
      await expect(checkboxes.nth(index)).toBeChecked();
    }

    await checkboxes.nth(0).click();
    await expect(checkboxes.nth(0)).not.toBeChecked();
    await rows.nth(2).locator('[col-id="description"]').click();
    await expect(checkboxes.nth(0)).not.toBeChecked();
    await expect(checkboxes.nth(1)).toBeChecked();
    await expect(checkboxes.nth(2)).toBeChecked();
  },
);
