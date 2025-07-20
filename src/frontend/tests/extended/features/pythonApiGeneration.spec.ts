import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "python_api_generation",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page, context }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.getByTestId("publish-button").click();
    await page.getByTestId("api-access-item").click();
    await page.getByTestId("api_tab_python").click();
    await page.getByTestId("icon-Copy").click();
    const handle = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent = await handle.jsonValue();
    expect(clipboardContent.length).toBeGreaterThan(0);
  },
);
