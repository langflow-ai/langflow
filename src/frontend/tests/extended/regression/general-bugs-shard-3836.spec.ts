import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";

test("user must be able to send an image on chat using advanced tool on ChatInputComponent", async ({
  page,
}) => {
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
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }

  await page
    .getByTestId("popover-anchor-input-api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByTestId("dropdown_str_model_name").click();
  await page.getByTestId("gpt-4o-1-option").click();

  await page.waitForSelector("text=Chat Input", { timeout: 30000 });

  await page.getByText("Chat Input", { exact: true }).click();
  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();
  await page.getByTestId("showfiles").click();
  await page.getByText("Close").last().click();

  await page.waitForTimeout(500);

  const userQuestion = "What is this image?";
  await page.getByTestId("textarea_str_input_value").fill(userQuestion);

  const filePath = "tests/assets/chain.png";

  await page.click('[data-testid="inputfile_file_files"]');

  const [fileChooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.click('[data-testid="inputfile_file_files"]'),
  ]);

  await fileChooser.setFiles(filePath);

  await page.keyboard.press("Escape");

  await page.getByTestId("button_run_chat output").click();
  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByText("Playground", { exact: true }).last().click();

  await page.waitForTimeout(500);

  await page.waitForSelector('[data-testid="icon-LucideSend"]', {
    timeout: 100000,
  });

  await page.waitForSelector("text=chain.png", { timeout: 30000 });

  expect(await page.getByAltText("generated image").isVisible()).toBeTruthy();

  expect(
    await page.getByTestId(`chat-message-User-${userQuestion}`).isVisible(),
  ).toBeTruthy();

  const textContents = await page
    .getByTestId("div-chat-message")
    .allTextContents();

  expect(textContents[0]).toContain("chain");
});
