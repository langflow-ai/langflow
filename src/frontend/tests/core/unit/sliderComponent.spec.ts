import { expect, Page, test } from "@playwright/test";
import uaParser from "ua-parser-js";

// TODO: This component doesn't have slider needs updating
test("user should be able to use slider input", async ({ page }) => {
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
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("ollama");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("modelsOllama")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  await page.getByTestId("title-Ollama").click();
  await page.getByTestId("code-button-modal").click();

  let cleanCode = await extractAndCleanCode(page);

  // Replace the import statement
  cleanCode = cleanCode.replace("FloatInput(", "SliderInput(");
  cleanCode = cleanCode.replace(
    "from langflow.io import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, StrInput",
    "from langflow.io import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, StrInput, SliderInput",
  );

  cleanCode = cleanCode.replace(
    "value=0.2,",
    "value=0.2, range_spec=RangeSpec(min=3, max=30, step=1), min_label='test', max_label='test2', min_label_icon='pencil-ruler', max_label_icon='palette', slider_buttons=False, slider_buttons_options=[], slider_input=False,",
  );

  await page.locator("textarea").last().press(`${control}+a`);
  await page.keyboard.press("Backspace");
  await page.locator("textarea").last().fill(cleanCode);
  await page.locator('//*[@id="checkAndSaveBtn"]').click();
  await page.waitForTimeout(500);

  await page.getByTestId("fit_view").click();

  await mutualValidation(page);

  await moveSlider(page, "right", false);

  await page.waitForTimeout(500);

  await page.getByTestId("zoom_out").click();

  await page.getByTestId("more-options-modal").click();
  await page.getByText("Controls", { exact: true }).last().click();
  await expect(
    page.getByTestId("default_slider_display_value_advanced"),
  ).toHaveText("19.00");

  await moveSlider(page, "left", true);
  // Wait for any potential updates
  await page.waitForTimeout(500);

  await expect(
    page.getByTestId("default_slider_display_value_advanced"),
  ).toHaveText("14.00");

  await page.getByText("Close").last().click();

  await expect(page.getByTestId("default_slider_display_value")).toHaveText(
    "14.00",
  );
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

async function mutualValidation(page: Page) {
  await expect(page.getByTestId("default_slider_display_value")).toHaveText(
    "3.00",
  );
  await expect(page.getByTestId("min_label")).toHaveText("test");
  await expect(page.getByTestId("max_label")).toHaveText("test2");
  await expect(page.getByTestId("icon-pencil-ruler")).toBeVisible();
  await expect(page.getByTestId("icon-palette")).toBeVisible();
}
async function moveSlider(
  page: Page,
  side: "left" | "right",
  advanced: boolean = false,
) {
  const thumbSelector = `slider_thumb${advanced ? "_advanced" : ""}`;
  const trackSelector = `slider_track${advanced ? "_advanced" : ""}`;

  await page.getByTestId(thumbSelector).click();

  const trackBoundingBox = await page.getByTestId(trackSelector).boundingBox();

  if (trackBoundingBox) {
    const moveDistance =
      trackBoundingBox.width * 0.1 * (side === "left" ? -1 : 1);
    const centerX = trackBoundingBox.x + trackBoundingBox.width / 2;
    const centerY = trackBoundingBox.y + trackBoundingBox.height / 2;

    await page.mouse.move(centerX + moveDistance, centerY);
    await page.mouse.down();
    await page.mouse.up();
  }
}
