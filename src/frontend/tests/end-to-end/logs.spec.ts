import { test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("should able to see and interact with logs", async ({ page }) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  if (!process.env.CI) {
    dotenv.config({ path: path.resolve(__dirname, "../../.env") });
  }

  await page.goto("/");
  await page.waitForTimeout(2000);

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
    await page.getByText("New Project", { exact: true }).click();

    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForTimeout(2000);

  await page.getByTestId("icon-ChevronDown").click();
  await page.getByText("Logs").click();
  await page.getByText("No Data Available", { exact: true }).isVisible();
  await page.keyboard.press("Escape");

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByTestId("dropdown-model_name").click();
  await page.getByTestId("gpt-4o-0-option").click();

  await page.waitForTimeout(2000);
  await page.getByTestId("button_run_chat output").first().click();

  await page.waitForTimeout(2000);
  await page
    .getByText("Chat Output built successfully", { exact: true })
    .isVisible();
  await page.getByTestId("icon-ChevronDown").click();
  await page.getByText("Logs").click();

  await page.getByText("timestamp").first().isVisible();
  await page.getByText("flow_id").first().isVisible();
  await page.getByText("source").first().isVisible();
  await page.getByText("target", { exact: true }).first().isVisible();
  await page.getByText("target_args", { exact: true }).first().isVisible();
  await page.getByRole("gridcell").first().isVisible();

  await page.keyboard.press("Escape");

  await page.getByTestId("user-profile-settings").first().click();
  await page.getByText("Settings", { exact: true }).click();

  await page.getByText("Messages", { exact: true }).click();
  await page.getByText("index", { exact: true }).last().isVisible();
  await page.getByText("timestamp", { exact: true }).isVisible();
  await page.getByText("flow_id", { exact: true }).isVisible();
  await page.getByText("source", { exact: true }).isVisible();
  await page.getByText("target", { exact: true }).isVisible();
  await page.getByText("vertex_id", { exact: true }).isVisible();
  await page.getByText("status", { exact: true }).isVisible();
  await page.getByText("error", { exact: true }).isVisible();
  await page.getByText("outputs", { exact: true }).isVisible();
  await page.getByText("inputs", { exact: true }).isVisible();

  await page.getByRole("gridcell").first().isVisible();
});
