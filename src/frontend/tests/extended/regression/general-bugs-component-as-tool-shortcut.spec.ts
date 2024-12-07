import { expect, test } from "@playwright/test";
import { extractAndCleanCode } from "../../utils/extract-and-clean-code";

test(
  "user must be able to use component as tool shortcut only if has tool mode is True",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await page.goto("/");
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
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("id generator");

    await page
      .getByTestId("helpersID Generator")
      .hover()
      .then(async () => {
        await page.getByTestId("add-component-button-id-generator").click();
      });

    await page.waitForSelector('[data-testid="title-ID Generator"]', {
      timeout: 3000,
    });

    expect(await page.getByText("Toolset", { exact: true }).count()).toBe(0);

    await page.getByTestId("title-ID Generator").click();
    await page.keyboard.press("ControlOrMeta+Shift+m");

    expect(await page.getByText("Toolset", { exact: true }).count()).toBe(0);

    await page.getByTestId("title-ID Generator").click();

    await page.waitForSelector('[data-testid="code-button-modal"]', {
      timeout: 3000,
    });

    await page.getByTestId("code-button-modal").click();

    let code = await extractAndCleanCode(page);
    code = code!.replace(
      "refresh_button=True,",
      "refresh_button=True,\n tool_mode=True,",
    );

    await page.locator("textarea").last().press(`ControlOrMeta+a`);
    await page.keyboard.press("Backspace");
    await page.locator("textarea").last().fill(code);
    await page.locator('//*[@id="checkAndSaveBtn"]').click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 3000,
    });

    await page.getByTestId("title-ID Generator").click();
    await page.keyboard.press("ControlOrMeta+Shift+m");

    await page.waitForSelector('text="Toolset"', {
      timeout: 3000,
    });

    expect(
      await page.getByText("Toolset", { exact: true }).count(),
    ).toBeGreaterThan(0);
  },
);
