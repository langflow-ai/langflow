import { test } from "@playwright/test";

test("should able to see and interact with logs", async ({ page }) => {
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
  await page.waitForTimeout(1000);

  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForTimeout(2000);

  await page.getByTestId("icon-ChevronDown").click();
  await page.getByText("Logs").click();
  await page.getByText("No Data Available", { exact: true }).isVisible();
  await page.keyboard.press("Escape");

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");
  await page.getByTestId("button_run_chat output").first().click();

  await page.waitForTimeout(2000);
  await page
    .getByText("Chat Output built successfully", { exact: true })
    .isVisible();
  await page.getByTestId("icon-ChevronDown").click();
  await page.getByText("Logs").click();

  await page.getByText("timestamp").isVisible();
  await page.getByText("flow_id").isVisible();
  await page.getByText("source").isVisible();
  await page.getByText("target", { exact: true }).isVisible();
  await page.getByText("target_args", { exact: true }).isVisible();
  await page.getByRole("gridcell").first().isVisible();

  await page.getByText("Messages", { exact: true }).click();
  await page.getByText("Index").isVisible();
  await page.getByText("Timestamp").isVisible();
  await page.getByText("Flow Id", { exact: true }).isVisible();
  await page.getByText("Source").isVisible();
  await page.getByText("Target", { exact: true }).isVisible();
  await page.getByText("Target Args", { exact: true }).isVisible();
  await page.getByText("Status", { exact: true }).isVisible();
  await page.getByText("Error", { exact: true }).isVisible();
  await page.getByRole("gridcell").first().isVisible();
});
