import { type Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  closeAdvancedOptions,
  disableInspectPanel,
  enableInspectPanel,
  openAdvancedOptions,
} from "../../utils/open-advanced-options";

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

    await page.waitForSelector('[data-testid="ollamaOllama"]', {
      timeout: 3000,
    });

    await page
      .getByTestId("ollamaOllama")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page, { numberOfZoomOut: 2 });

    await page.getByTestId("title-Ollama").click();
    await page.getByTestId("code-button-modal").last().click();

    const cleanCode = await extractAndCleanCode(page);

    // Replace the multiline string in the code.
    // Use a regex so the match is resilient to line-ending differences
    // (LF on macOS/Linux vs CRLF on Windows after git checkout).
    const originalSliderBlockRegex =
      /name="temperature",\s+display_name="Temperature",\s+value=0\.1,\s+range_spec=RangeSpec\(min=0, max=1, step=0\.01\),\s+advanced=True,/;
    const newCode = cleanCode.replace(
      originalSliderBlockRegex,
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
    await setAceEditorValue(page, newCode);
    await page.locator('//*[@id="checkAndSaveBtn"]').click();
    await adjustScreenView(page);

    await mutualValidation(page);

    await moveSlider(page, "right", false);

    // wait for the slider to update

    await page.waitForTimeout(500);
    await adjustScreenView(page, { numberOfZoomOut: 1 });

    await disableInspectPanel(page);

    await openAdvancedOptions(page);
    await expect(
      page.getByTestId("default_slider_display_value_advanced"),
    ).toHaveText("19.00");

    await moveSlider(page, "left", true);
    // Wait for any potential updates
    await page.waitForTimeout(500);

    await expect(
      page.getByTestId("default_slider_display_value_advanced"),
    ).toHaveText("14.00");

    await closeAdvancedOptions(page);

    await expect(page.getByTestId("default_slider_display_value")).toHaveText(
      "14.00",
    );

    await enableInspectPanel(page);
  },
);

async function extractAndCleanCode(page: Page): Promise<string> {
  const codeContent = await page
    .locator('//*[@id="codeValue"]')
    .evaluate((el) => (el as HTMLInputElement).value);

  // Normalize line endings so downstream string operations are OS-agnostic
  // (Windows git checkouts of .py files can end up with CRLF).
  return codeContent.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

// Reliably replace the Ace editor content. The keyboard-based approaches are
// all flaky on at least one platform: locator.fill() bypasses Ace's internal
// buffer so the editor never sees the change, keyboard.insertText() drops
// embedded "\n" characters on Windows (flattening the code into a single
// invalid line), and pressSequentially() triggers Ace's Python auto-indent and
// corrupts whitespace. Instead, drive Ace through its own API: ace-builds
// exposes `window.ace` globally and `ace.edit(element)` returns the existing
// editor instance, so setValue() applies the change atomically.
async function setAceEditorValue(page: Page, newCode: string): Promise<void> {
  await page.locator(".ace_editor").first().waitFor({ state: "visible" });
  await page.evaluate((code) => {
    const aceEl = document.querySelector(".ace_editor");
    const globalAce = (window as unknown as { ace?: { edit: (el: Element) => { setValue: (v: string, cursorPos?: number) => void } } }).ace;
    if (!aceEl || !globalAce) {
      throw new Error("Ace editor not found on the page");
    }
    globalAce.edit(aceEl).setValue(code, -1);
  }, newCode);

  // Wait for Ace to propagate the change to the controlled React state so the
  // hidden #codeValue mirror contains the expected value before we save.
  await expect(page.locator("#codeValue")).toHaveValue(
    /range_spec=RangeSpec\(min=3, max=30, step=1\)/,
    { timeout: 10000 },
  );
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
