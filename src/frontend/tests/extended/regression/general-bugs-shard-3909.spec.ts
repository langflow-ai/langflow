import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test(
  "user must be able to create a new flow clicking on New Flow button",
  { tag: ["@release"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }

    await page.goto("/");

    await page.waitForTimeout(1000);

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

    await page.getByText("Close").last().click();

    await page.getByTestId("add-folder-button").click();

    await page.getByText("New Folder").last().click();

    await page.waitForSelector("text=new flow", { timeout: 30000 });

    await page.waitForTimeout(1000);

    expect(
      (
        await page.waitForSelector("text=new flow", {
          timeout: 30000,
        })
      ).isVisible(),
    );

    await page.getByText("New Flow", { exact: true }).click();

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.waitForSelector("text=playground", { timeout: 30000 });
    await page.waitForSelector("text=api", { timeout: 30000 });
    await page.waitForSelector("text=share", { timeout: 30000 });

    await page.waitForTimeout(1000);

    expect(
      await page.getByTestId("button_run_chat output").isVisible(),
    ).toBeTruthy();
    expect(
      await page.getByTestId("button_run_openai").isVisible(),
    ).toBeTruthy();
    expect(
      await page.getByTestId("button_run_prompt").isVisible(),
    ).toBeTruthy();
    expect(
      await page.getByTestId("button_run_chat input").isVisible(),
    ).toBeTruthy();
  },
);
