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
  // The hidden `#codeValue` mirror is rendered with `<Input value={code} />`,
  // i.e. a single-line `<input>` rather than a textarea. Browsers strip
  // newlines from `.value` of single-line inputs by HTML spec, so reading
  // `(el as HTMLInputElement).value` returns the entire source concatenated
  // onto one line. The backend then rejects it as
  // `invalid decimal literal (<unknown>, line 1)`.
  //
  // Read the rendered HTML attribute instead — React serializes the prop as
  // `value="..."` with newlines encoded (`&#10;`, `&#13;`, or literal LF
  // inside attribute text), and the regex below recovers them faithfully.
  // This is the same strategy queryInputComponent.spec.ts uses.
  const outerHTML = await page
    .locator('//*[@id="codeValue"]')
    .evaluate((el) => el.outerHTML);

  const valueMatch = outerHTML.match(/value="([\s\S]*?)"/);
  if (!valueMatch) {
    throw new Error("Could not find value attribute in the #codeValue HTML");
  }

  const codeContent = valueMatch[1]
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#x27;/g, "'")
    .replace(/&#x2F;/g, "/")
    .replace(/&#10;/g, "\n")
    .replace(/&#13;/g, "\r")
    .replace(/&#xA;/gi, "\n")
    .replace(/&#xD;/gi, "\r");

  // Normalize line endings so downstream string operations are OS-agnostic
  // (Windows git checkouts of .py files can end up with CRLF).
  return codeContent.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

// Reliably replace the Ace editor content cross-platform. Every keyboard route
// fails on at least one OS: locator.fill() bypasses Ace's internal buffer,
// keyboard.insertText() silently drops embedded "\n" characters on Windows
// (flattening the code into a single invalid line — the `invalid decimal
// literal (<unknown>, line 1)` failure mode), and pressSequentially() triggers
// Ace's Python auto-indent and corrupts whitespace.
//
// Instead, drive Ace via its own API: ace-builds exposes `window.ace` and
// `ace.edit(element)` returns the existing editor instance, so setValue()
// applies the change atomically. We also assert at each step that newlines
// survived, so a future regression surfaces a precise diagnostic instead of
// the same opaque backend 400.
async function setAceEditorValue(page: Page, newCode: string): Promise<void> {
  const expectedNewlines = (newCode.match(/\n/g) || []).length;
  if (expectedNewlines < 10) {
    throw new Error(
      `setAceEditorValue: newCode has only ${expectedNewlines} newlines (length ${newCode.length}); the slider replacement template alone should produce >=11. Upstream extractAndCleanCode likely lost newlines.`,
    );
  }

  await page.locator(".ace_editor").first().waitFor({ state: "visible" });

  const result = await page.evaluate(
    ({ code, expectedNewlines }) => {
      const aceEl = document.querySelector(".ace_editor");
      const globalAce = (
        window as unknown as {
          ace?: {
            edit: (el: Element) => {
              setValue: (v: string, cursorPos?: number) => void;
              getValue: () => string;
              session: { setNewLineMode: (mode: string) => void };
            };
          };
        }
      ).ace;

      if (!aceEl) return { ok: false as const, reason: "ace_editor element not found" };
      if (!globalAce?.edit)
        return { ok: false as const, reason: "window.ace not exposed" };

      const incomingNewlines = (code.match(/\n/g) || []).length;
      if (incomingNewlines !== expectedNewlines) {
        return {
          ok: false as const,
          reason: `newlines lost crossing into evaluate: expected ${expectedNewlines}, got ${incomingNewlines}`,
        };
      }

      const editor = globalAce.edit(aceEl);
      // Force LF so getValue() returns exactly what we set, regardless of the
      // platform's autodetected line ending.
      editor.session.setNewLineMode("unix");
      editor.setValue(code, -1);

      const out = editor.getValue();
      const outNewlines = (out.match(/\n/g) || []).length;
      return {
        ok: true as const,
        incomingNewlines,
        outNewlines,
        outLength: out.length,
      };
    },
    { code: newCode, expectedNewlines },
  );

  if (!result.ok) {
    throw new Error(`setAceEditorValue: ${result.reason}`);
  }
  if (result.outNewlines < result.incomingNewlines) {
    throw new Error(
      `Ace dropped newlines: setValue input had ${result.incomingNewlines}, getValue returned ${result.outNewlines} (length ${result.outLength}).`,
    );
  }

  // Wait for Ace's change event to propagate into the controlled React state.
  // We can't compare newline counts on the mirror's `.value` because
  // `#codeValue` is rendered by `<Input>` (a single-line input element) and
  // browsers strip `\n`/`\r` from `.value` of single-line inputs by spec —
  // newlines DO survive in React state, they just don't show up via that
  // property. The regex marker below is enough to confirm the new code
  // landed; the `value="..."` HTML attribute on the input still carries the
  // full multi-line source for any downstream test that needs to read it.
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
