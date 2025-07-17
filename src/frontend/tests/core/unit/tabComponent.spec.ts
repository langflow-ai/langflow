import { expect, type Page, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should interact with tab component",
  { tag: ["@release", "@workspace"] },
  async ({ context, page }) => {
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
    await page.getByTitle("fit view").click();
    await page.getByTitle("zoom out").click();

    await page.getByTestId("title-Custom Component").first().click();

    await page.waitForSelector('[data-testid="code-button-modal"]', {
      timeout: 3000,
    });

    await page.getByTestId("code-button-modal").click();

    let cleanCode = await extractAndCleanCode(page);

    // Use regex pattern to match the imports section more flexibly
    cleanCode = updateComponentCode(cleanCode, {
      imports: ["MessageTextInput", "Output", "TabInput"],
      inputs: [
        {
          name: "MessageTextInput",
          config: {
            name: "input_value",
            display_name: "Input Value",
            info: "This is a custom component Input",
            value: "Hello, World!",
            tool_mode: true,
          },
        },
        {
          name: "TabInput",
          config: {
            name: "tab_selection",
            display_name: "Tab Selection",
            options: ["Tab 1", "Tab 2", "Tab 3"],
            value: "Tab 1",
          },
        },
      ],
    });

    await page.locator("textarea").last().press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");
    await page.locator("textarea").last().fill(cleanCode);
    await page.locator('//*[@id="checkAndSaveBtn"]').click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 3000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();

    // Verify that all tabs are visible
    expect(await page.getByText("Tab 1").isVisible()).toBeTruthy();
    expect(await page.getByText("Tab 2").isVisible()).toBeTruthy();
    expect(await page.getByText("Tab 3").isVisible()).toBeTruthy();

    // Verify that Tab 1 is active by default (as specified in the value)
    expect(
      await page
        .getByRole("tab", { name: "Tab 1", selected: true })
        .isVisible(),
    ).toBeTruthy();

    // Click on Tab 2 and verify it becomes active
    await page.getByRole("tab", { name: "Tab 2" }).click();
    expect(
      await page
        .getByRole("tab", { name: "Tab 2", selected: true })
        .isVisible(),
    ).toBeTruthy();

    // Click on Tab 3 and verify it becomes active
    await page.getByRole("tab", { name: "Tab 3" }).click();
    expect(
      await page
        .getByRole("tab", { name: "Tab 3", selected: true })
        .isVisible(),
    ).toBeTruthy();
  },
);

async function extractAndCleanCode(page: Page): Promise<string> {
  const outerHTML = await page
    .locator('//*[@id="codeValue"]')
    .evaluate((el) => el.outerHTML);

  const valueMatch = outerHTML.match(/value="([\s\S]*?)"/);
  if (!valueMatch) {
    throw new Error("Could not find value attribute in the HTML");
  }

  const codeContent = valueMatch[1]
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, "/");

  return codeContent;
}

function updateComponentCode(
  code: string,
  updates: {
    imports?: string[];
    inputs?: Array<{ name: string; config: Record<string, any> }>;
  },
): string {
  let updatedCode = code;

  // Update imports
  if (updates.imports) {
    const importPattern = /from\s+langflow\.io\s+import\s+([^;\n]+)/;
    const newImports = updates.imports.join(", ");
    updatedCode = updatedCode.replace(
      importPattern,
      `from langflow.io import ${newImports}`,
    );
  }

  // Update inputs
  if (updates.inputs) {
    const inputsPattern = /inputs\s*=\s*\[([\s\S]*?)\]/;
    const newInputs = updates.inputs
      .map(({ name, config }) => {
        const params = Object.entries(config)
          .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
          .join(",\n            ");
        return `        ${name}(\n            ${params}\n        )`;
      })
      .join(",\n");
    updatedCode = updatedCode.replace(
      inputsPattern,
      `inputs = [\n${newInputs}\n    ]`,
    );
    updatedCode = updatedCode.replace("true", "True");
    updatedCode = updatedCode.replace("false", "False");
  }

  return updatedCode;
}
