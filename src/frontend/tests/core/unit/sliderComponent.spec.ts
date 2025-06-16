import { expect, Page, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// TODO: This component doesn't have slider needs updating
test(
  "user should be able to use slider input",
  {
    tag: ["@release", "@workspace"],
  },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("ollama");

    await page.waitForSelector('[data-testid="languagemodelsOllama"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("languagemodelsOllama")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("title-Ollama").click();
    await page.getByTestId("code-button-modal").click();

    let cleanCode = await extractAndCleanCode(page);

    // Replace the multiline string in the code
    const newCode = cleanCode.replace(
      `name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,`,
      `name="temperature",
            display_name="Temperature",
            value=0.2,
            range_spec=RangeSpec(min=3, max=30, step=1),
            min_label="test",
            max_label="test2",
            min_label_icon="pencil-ruler",
            max_label_icon="palette",
            slider_buttons=False,
            slider_buttons_options=[],
            slider_input=False,
            advanced=False,`,
    );
    // make sure codes are different
    expect(cleanCode).not.toEqual(newCode);
    await page.locator("textarea").last().press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");
    await page.locator("textarea").last().fill(newCode);
    await page.locator('//*[@id="checkAndSaveBtn"]').click();

    await page.getByTestId("fit_view").click();

    await mutualValidation(page);

    await moveSlider(page, "right", false);

    // wait for the slider to update

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
