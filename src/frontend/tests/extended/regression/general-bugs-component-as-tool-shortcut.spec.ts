import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { extractAndCleanCode } from "../../utils/extract-and-clean-code";

test(
  "user must be able to use component as tool shortcut only if has tool mode is True",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("prompt");

    await page
      .getByTestId("promptsPrompt")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-prompt").click();
      });

    await page.waitForSelector('[data-testid="title-Prompt"]', {
      timeout: 3000,
    });

    expect(await page.getByText("Toolset", { exact: true }).count()).toBe(0);

    await page.getByTestId("title-Prompt").click();
    await page.keyboard.press("ControlOrMeta+Shift+m");

    await page.waitForSelector('text="Toolset"', {
      timeout: 3000,
    });
    expect(
      await page.getByText("Toolset", { exact: true }).count(),
    ).toBeGreaterThan(0);

    await page.getByTestId("title-Prompt").click();

    await page.waitForSelector('[data-testid="code-button-modal"]', {
      timeout: 3000,
    });

    await page.getByTestId("code-button-modal").click();

    let code = await extractAndCleanCode(page);
    let updatedCode = code!.replace("tool_mode=True", "tool_mode=False");

    expect(updatedCode).not.toBe(code);

    await page.locator("textarea").last().press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");
    await page.locator("textarea").last().fill(updatedCode);
    const customComponentPromise = page.waitForResponse("**/custom_component");
    await page.locator('//*[@id="checkAndSaveBtn"]').click();
    const customComponentResponse = await customComponentPromise;
    // check if the response is 200
    expect(customComponentResponse?.status()).toBe(200);

    await page.waitForSelector('[data-testid="title-Prompt"]', {
      timeout: 3000,
    });

    await page.getByTestId("title-Prompt").click();
    await page.keyboard.press("ControlOrMeta+Shift+m");

    expect(await page.getByText("Toolset", { exact: true }).count()).toBe(0);
  },
);
