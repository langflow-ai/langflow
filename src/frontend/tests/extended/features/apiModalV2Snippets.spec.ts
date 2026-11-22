import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";

// The v2 snippets come in two blocks: "Get the full result" and "Stream the
// result as it runs". The second block once collapsed to 0 px whenever the
// first one filled the modal, so it could be neither seen nor copied.
const VIEWPORTS = [
  { width: 1280, height: 720 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
];
const LANGUAGES = ["python", "javascript", "curl"];

for (const viewport of VIEWPORTS) {
  test(
    `v2 API snippets show both blocks at ${viewport.width}x${viewport.height}`,
    { tag: ["@release", "@api", "@workspace"] },
    async ({ page }) => {
      await page.setViewportSize(viewport);
      await awaitBootstrapTest(page);

      await page.getByTestId("side_nav_options_all-templates").click();
      await page
        .getByRole("heading", { name: TEXTS.templateBasicPrompting })
        .click();
      // Let the template finish loading, including its component updates.
      await page.waitForSelector('text="Loading"', {
        state: "hidden",
        timeout: 60000,
      });
      await page.waitForSelector('[data-testid="publish-button"]', {
        timeout: 30000,
      });
      await page.getByTestId("publish-button").click();
      await page.getByTestId("api-access-item").click();

      // The modal opens on v2.
      await expect(page.getByTestId("api_version_v2")).toHaveAttribute(
        "data-state",
        "active",
      );

      for (const language of LANGUAGES) {
        await page.getByTestId(`api_tab_${language}`).click();

        const streamBlock = page.getByTestId("api-step-2");
        await streamBlock.scrollIntoViewIfNeeded();
        const box = await streamBlock.boundingBox();
        expect(box?.height ?? 0).toBeGreaterThan(100);

        const copyStream = page.getByTestId("btn-copy-step2");
        await expect(copyStream).toBeVisible();
        await copyStream.click();
        const copied = await page.evaluate(() =>
          navigator.clipboard.readText(),
        );
        expect(copied).toContain("stream");
      }
    },
  );
}
