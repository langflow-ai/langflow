import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import { readFileSync } from "fs";
import path from "path";

test("user must interact with chat with Input/Output", async ({ page }) => {
  if (!process.env.CI) {
    dotenv.config();
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
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByRole("heading", { name: "Basic Prompting" }).click();
  await page.waitForTimeout(1000);

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  if (!process.env.OPENAI_API_KEY) {
    //You must set the OPENAI_API_KEY on .env file to run this test
    expect(false).toBe(true);
  }

  await page
    .getByTestId("input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");
  await page.getByText("Playground", { exact: true }).click();
  await page.getByPlaceholder("Send a message...").fill("Hello, how are you?");
  await page.getByTestId("icon-LucideSend").click();
  let valueUser = await page.getByTestId("sender_name_user").textContent();
  let valueAI = await page.getByTestId("sender_name_ai").textContent();

  expect(valueUser).toBe("User");
  expect(valueAI).toBe("AI");

  await page.keyboard.press("Escape");

  await page
    .getByTestId("textarea-input_value")
    .nth(1)
    .fill(
      "testtesttesttesttesttestte;.;.,;,.;,.;.,;,..,;;;;;;;;;;;;;;;;;;;;;,;.;,.;,.,;.,;.;.,~~çççççççççççççççççççççççççççççççççççççççisdajfdasiopjfaodisjhvoicxjiovjcxizopjviopasjioasfhjaiohf23432432432423423sttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttestççççççççççççççççççççççççççççççççç,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,!"
    );
  await page.getByTestId("input-sender_name").nth(1).fill("TestSenderNameUser");
  await page.getByTestId("input-sender_name").nth(0).fill("TestSenderNameAI");

  await page.getByText("Playground", { exact: true }).click();
  await page.getByTestId("icon-LucideSend").click();

  valueUser = await page
    .getByTestId("sender_name_testsendernameuser")
    .textContent();
  valueAI = await page
    .getByTestId("sender_name_testsendernameai")
    .textContent();

  expect(valueUser).toBe("TestSenderNameUser");
  expect(valueAI).toBe("TestSenderNameAI");

  expect(
    await page
      .getByText(
        "testtesttesttesttesttestte;.;.,;,.;,.;.,;,..,;;;;;;;;;;;;;;;;;;;;;,;.;,.;,.,;.,;.;.,~~çççççççççççççççççççççççççççççççççççççççisdajfdasiopjfaodisjhvoicxjiovjcxizopjviopasjioasfhjaiohf23432432432423423sttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttesttestççççççççççççççççççççççççççççççççç,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,.,!",
        { exact: true }
      )
      .isVisible()
  );
});

test("chat_io_teste", async ({ page }) => {
  await page.goto("/");
  await page.locator("span").filter({ hasText: "My Collection" }).isVisible();
  // Read your file into a buffer.
  const jsonContent = readFileSync(
    "tests/end-to-end/assets/ChatTest.json",
    "utf-8"
  );

  await page.waitForTimeout(3000);

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
    await page.locator('//*[@id="new-project-btn"]').click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(2000);

  // Create the DataTransfer and File
  const dataTransfer = await page.evaluateHandle((data) => {
    const dt = new DataTransfer();
    // Convert the buffer to a hex array
    const file = new File([data], "ChatTest.json", {
      type: "application/json",
    });
    dt.items.add(file);
    return dt;
  }, jsonContent);

  // Now dispatch
  await page.dispatchEvent(
    '//*[@id="react-flow-id"]/div[1]/div[1]/div',
    "drop",
    {
      dataTransfer,
    }
  );
  await page.getByLabel("fit view").click();
  await page.getByText("Playground", { exact: true }).click();
  await page.getByPlaceholder("Send a message...").click();
  await page.getByPlaceholder("Send a message...").fill("teste");
  await page.getByRole("button").nth(1).click();
  const chat_output = page.getByTestId("chat-message-AI-teste");
  const chat_input = page.getByTestId("chat-message-User-teste");
  await expect(chat_output).toHaveText("teste");
  await expect(chat_input).toHaveText("teste");
});
