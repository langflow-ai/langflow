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
  let control = "Control";

  if (userAgentInfo.os.name.includes("Mac")) {
    control = "Meta";
  }

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

  // Replace the import statement
  cleanCode = cleanCode.replace(
    "from langflow.io import MessageTextInput, Output",
    "from langflow.io import MessageTextInput, Output, LinkInput",
  );

  // Replace the MessageTextInput line and add LinkInput
  cleanCode = cleanCode.replace(
    'MessageTextInput(name="input_value", display_name="Input Value", value="Hello, World!"),',
    `MessageTextInput(name="input_value", display_name="Input Value", value="Hello, World!"),
    LinkInput(name="link", display_name="BUTTON", value="https://www.datastax.com", text="Click me"),`,
  );

  await page.locator("textarea").last().press(`${control}+a`);
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
