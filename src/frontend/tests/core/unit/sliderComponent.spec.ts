import { type Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { extractAndCleanCode } from "../../utils/extract-and-clean-code";
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

    // Sanity-check: the original Ollama source has many lines. If we read it
    // back as a single concatenated line, the textarea-value path is the
    // problem and Ace surgery downstream cannot save us.
    const cleanCodeNewlines = (cleanCode.match(/\n/g) || []).length;
    if (cleanCodeNewlines < 50) {
      throw new Error(
        `extractAndCleanCode returned code with only ${cleanCodeNewlines} newlines (length ${cleanCode.length}); expected the multi-line Ollama source. The hidden #codeValue textarea may be returning a stripped value on this platform.`,
      );
    }

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

    // Wait for the code modal to CLOSE before validating the node. The modal
    // only closes on a successful save (processDynamicField → setOpen(false));
    // if validation fails it stays open showing an error. Asserting the close
    // first (a) confirms the new code actually committed, and (b) makes a save
    // failure surface here with a clear signal instead of downstream as a
    // confusing stale-slider value. On a slow Windows runner the node re-render
    // also lags the click, so this doubles as the settle wait.
    await expect(page.locator('//*[@id="checkAndSaveBtn"]')).toBeHidden({
      timeout: 15000,
    });
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

// Set the Ace editor's content using the exact same pattern that
// queryInputComponent.spec.ts uses successfully on Windows CI:
// `textarea.last().fill(newCode)` against Ace's hidden text-input textarea.
// Textareas (unlike single-line `<input>`s) preserve `\n` in `.value`, so
// fill() reliably round-trips the multi-line source. Ace's text-input
// listener picks up the resulting `input` event, applies it to the buffer,
// and fires the `change` event that react-ace listens to — which is what
// updates the React `code` state that gets POSTed on save.
async function setAceEditorValue(page: Page, newCode: string): Promise<void> {
  // Normalize to LF before filling. A Windows checkout (autocrlf) or the
  // extract→replace round-trip can introduce CRLF; feeding mixed line endings
  // through Ace's hidden textarea has produced a saved buffer that diverges
  // from the asserted code on Windows. LF round-trips identically everywhere.
  const normalizedCode = newCode.replace(/\r\n/g, "\n");
  const expectedNewlines = (normalizedCode.match(/\n/g) || []).length;
  if (expectedNewlines < 10) {
    throw new Error(
      `setAceEditorValue: newCode has only ${expectedNewlines} newlines (length ${normalizedCode.length}); upstream extractAndCleanCode likely lost newlines.`,
    );
  }

  await page.locator("textarea").last().press("ControlOrMeta+a");
  await page.keyboard.press("Backspace");
  await page.locator("textarea").last().fill(normalizedCode);

  // Wait for the change to propagate into the controlled React state. The
  // `#codeValue` mirror is rendered by `<Input>` (single-line), so browsers
  // strip newlines from its `.value` — matching the substring is enough to
  // confirm the new code landed.
  await expect(page.locator("#codeValue")).toHaveValue(
    /range_spec=RangeSpec\(min=3, max=30, step=1\)/,
    { timeout: 10000 },
  );
}

async function mutualValidation(page: Page) {
  // Longer timeout on the first post-save assertion: the slider only reflects
  // the new range_spec (min=3, which clamps the preserved value to 3.00) once
  // the node has fully re-rendered with the saved code. That re-render lags on
  // a slow Windows runner; the default 5s poll can read the pre-save value.
  await expect(page.getByTestId("default_slider_display_value")).toHaveText(
    "3.00",
    { timeout: 15000 },
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
