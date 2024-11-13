import { expect, Page, test } from "@playwright/test";
import uaParser from "ua-parser-js";

// TODO: This test might not be needed anymore
test("user should interact with link component", async ({ context, page }) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Flow", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  const getUA = await page.evaluate(() => navigator.userAgent);
  const userAgentInfo = uaParser(getUA);

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });
  await page.getByTestId("blank-flow").click();

  await page.waitForTimeout(1000);

  await page.getByTestId("sidebar-custom-component-button").click();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();

  await page.getByTestId("title-Custom Component").first().click();

  await page.waitForTimeout(500);
  await page.getByTestId("code-button-modal").click();
  await page.waitForTimeout(500);

  let cleanCode = await extractAndCleanCode(page);

  // Use regex pattern to match the imports section more flexibly
  cleanCode = updateComponentCode(cleanCode, {
    imports: ["MessageTextInput", "Output", "LinkInput"],
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
        name: "LinkInput",
        config: {
          name: "link",
          display_name: "BUTTON",
          value: "https://www.datastax.com",
          text: "Click me",
        },
      },
    ],
  });

  await page.locator("textarea").last().press(`ControlOrMeta+a`);
  await page.keyboard.press("Backspace");
  await page.locator("textarea").last().fill(cleanCode);
  await page.locator('//*[@id="checkAndSaveBtn"]').click();
  await page.waitForTimeout(500);

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();

  expect(await page.getByText("BUTTON").isVisible()).toBeTruthy();
  expect(await page.getByText("Click me").isVisible()).toBeTruthy();
  expect(await page.getByTestId("link_link_link")).toBeEnabled();
  await page.getByTestId("link_link_link").click();
});

async function extractAndCleanCode(page: Page): Promise<string> {
  const outerHTML = await page
    .locator('//*[@id="codeValue"]')
    .evaluate((el) => el.outerHTML);

  const valueMatch = outerHTML.match(/value="([\s\S]*?)"/);
  if (!valueMatch) {
    throw new Error("Could not find value attribute in the HTML");
  }

  let codeContent = valueMatch[1]
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
