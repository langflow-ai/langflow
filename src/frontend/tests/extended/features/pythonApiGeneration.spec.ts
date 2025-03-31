import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "python_api_generation",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page, context }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.getByText("API", { exact: true }).click();
    await page.getByRole("tab", { name: "Python API" }).click();
    await page.getByTestId("icon-Copy").click();
    const handle = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent = await handle.jsonValue();
    expect(clipboardContent.length).toBeGreaterThan(0);
  },
);
