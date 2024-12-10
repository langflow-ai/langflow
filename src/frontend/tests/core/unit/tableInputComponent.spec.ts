import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to interact with table input component",
  {
    tag: ["@release", "@workspace"],
  },
  async ({ page }) => {
    const randomText = Math.random().toString(36).substring(7);
    const secondRandomText = Math.random().toString(36).substring(7);
    const thirdRandomText = Math.random().toString(36).substring(7);

    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await page.waitForSelector(
      '[data-testid="sidebar-custom-component-button"]',
      {
        timeout: 3000,
      },
    );

    await page.getByTestId("sidebar-custom-component-button").click();

    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("div-generic-node").click();
    await page.getByTestId("code-button-modal").click();

    const customCodeWithError = `
# from langflow.field_typing import Data
from langflow.custom import Component
from langflow.io import TableInput, Output
from langflow.schema import Data


class CustomComponent(Component):
    display_name = "Custom Component"
    description = "Use as a template to create your own component."
    documentation: str = "http://docs.langflow.org/components/custom"
    icon = "custom_components"
    name = "CustomComponent"

    inputs = [
        TableInput(
    name="input_value",
    display_name="Input Value",
    value=[
        {"alpha": "X1", "bravo": "Y2", "charlie": "Z3", "delta": "W4", "echo": "V5"},
        {"alpha": "A6", "bravo": "B7", "charlie": "C8", "delta": "D9", "echo": "E0"},
        {"alpha": "F1", "bravo": "G2", "charlie": "H3", "delta": "I4", "echo": "J5"},
        {"alpha": "K6", "bravo": "L7", "charlie": "M8", "delta": "N9", "echo": "O0"},
        {"alpha": "P1", "bravo": "Q2", "charlie": "R3", "delta": "S4", "echo": "T5"}
    ],
    table_schema=[
        {"name": "alpha", "display_name": "Alpha"},
        {"name": "bravo", "display_name": "Bravo"},
        {"name": "charlie", "display_name": "Charlie"},
        {"name": "delta", "display_name": "Delta"},
        {"name": "echo", "display_name": "Echo"}
    ]
)
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    def build_output(self) -> Data:
        data = Data(value=self.input_value)
        self.status = data
        return data
  `;

    await page.locator("textarea").press(`ControlOrMeta+a`);
    await page.locator("textarea").fill(customCodeWithError);

    await page.getByText("Check & Save").last().click();

    await page.waitForSelector('text="Open Table"', {
      timeout: 3000,
    });

    await page.getByText("Open Table").click();

    await page.waitForSelector(".ag-cell-value", {
      timeout: 3000,
    });

    const visibleTextsGroup1 = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"];
    const visibleTextsGroup2 = ["X1", "Y2", "Z3", "W4", "V5"];
    const visibleTextsGroup3 = ["P1", "Q2", "R3", "S4", "T5"];
    const visibleTextsGroup4 = ["F1", "G2", "H3", "I4", "J5"];

    const allVisibleTexts = [
      ...visibleTextsGroup1,
      ...visibleTextsGroup2,
      ...visibleTextsGroup3,
      ...visibleTextsGroup4,
    ];

    for (const text of allVisibleTexts) {
      await expect(page.getByText(text).last()).toBeVisible();
    }

    await page.locator(".ag-cell-value").first().click();

    await page.getByPlaceholder("Empty").fill(randomText);
    await page.getByText("Save").last().click();
    await expect(page.getByTestId("icon-Type")).toBeHidden({
      timeout: 2000,
    });
    await page.locator(".ag-cell-value").nth(12).click();

    await page.getByPlaceholder("Empty").fill(secondRandomText);
    await page.getByText("Save").last().click();
    await expect(page.getByTestId("icon-Type")).toBeHidden({
      timeout: 2000,
    });

    await page.locator(".ag-cell-value").nth(24).click();
    await expect(page.getByTestId("icon-Type")).toBeVisible({
      timeout: 2000,
    });

    await page.getByPlaceholder("Empty").fill(thirdRandomText);
    await page.getByText("Save").last().click();

    await expect(page.getByTestId("icon-Type")).toBeHidden({
      timeout: 2000,
    });

    expect(page.getByText(randomText)).toBeVisible();
    expect(page.getByText(secondRandomText)).toBeVisible();
    expect(page.getByText(thirdRandomText)).toBeVisible();

    await page.locator('input[type="checkbox"]').last().click();

    await page.getByTestId("icon-Copy").last().click();

    await expect(page.getByTestId("duplicate-row-button")).toBeDisabled({
      timeout: 1000,
    });

    let numberOfCopiedRows = await page.getByText(thirdRandomText).count();
    expect(numberOfCopiedRows).toBe(2);

    await page.locator('input[type="checkbox"]').last().click();
    await page.getByTestId("icon-Trash2").last().click();

    await expect(page.getByTestId("delete-row-button")).toBeDisabled({
      timeout: 1000,
    });

    await page.locator('input[type="checkbox"]').last().click();
    await page.getByTestId("icon-Trash2").click();

    numberOfCopiedRows = await page.getByText(thirdRandomText).count();
    expect(numberOfCopiedRows).toBe(0);

    await page.getByText("Close").last().click();

    await page.waitForSelector("text=Open Table", {
      timeout: 3000,
    });

    await page.getByText("Open Table").click();

    await page.waitForSelector(".ag-cell-value", {
      timeout: 3000,
    });

    const visibleTexts = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"];
    const notVisibleTexts = ["X1", "thirdRandomText"];

    await Promise.all(
      visibleTexts.map((text) => expect(page.getByText(text)).toBeVisible()),
    );
    await Promise.all(
      notVisibleTexts.map((text) =>
        expect(page.getByText(text)).not.toBeVisible(),
      ),
    );
  },
);
