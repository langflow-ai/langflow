import { expect, test } from "@playwright/test";
import path from "path";

test("Basic Prompting (Hello, World)", async ({ page }) => {
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
    .getByTestId("popover-anchor-input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByTestId("button_run_chat output").click();
  await page.waitForTimeout(1000);
  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByText("Playground", { exact: true }).click();
  await page
    .getByText("No input message provided.", { exact: true })
    .last()
    .isVisible();
  await page
    .getByPlaceholder("Send a message...")
    .last()
    .fill("Say hello as a pirate");
  await page.getByTestId("icon-LucideSend").last().click();
  await page.waitForTimeout(3000);

  await page.getByText("Ahoy").last().isVisible();
  await page.getByText("Default Session").last().click();

  await page.getByText("timestamp", { exact: true }).last().isVisible();
  await page.getByText("text", { exact: true }).last().isVisible();
  await page.getByText("sender", { exact: true }).last().isVisible();
  await page.getByText("sender_name", { exact: true }).last().isVisible();
  await page.getByText("session_id", { exact: true }).last().isVisible();
  await page.getByText("files", { exact: true }).last().isVisible();

  await page.getByRole("gridcell").last().isVisible();
  await page.getByTestId("icon-Trash2").first().click();
  await page.getByPlaceholder("Send a message...").last().isVisible();
});

test("Memory Chatbot", async ({ page }) => {
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

  await page.getByRole("heading", { name: "Memory Chatbot" }).click();
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
    .getByTestId("popover-anchor-input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page.getByTestId("button_run_chat output").click();
  await page.waitForTimeout(1000);
  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByText("Playground", { exact: true }).click();
  await page
    .getByText("No input message provided.", { exact: true })
    .last()
    .isVisible();
  await page
    .getByPlaceholder("Send a message...")
    .last()
    .fill("Remember that I'm a lion");
  await page.getByTestId("icon-LucideSend").last().click();
  await page.waitForTimeout(3000);
  await page
    .getByPlaceholder("Send a message...")
    .last()
    .fill("try reproduce the sound I made in words");
  await page.getByTestId("icon-LucideSend").last().click();
  await page.waitForTimeout(3000);
  await page.getByText("roar").last().isVisible();
  await page.getByText("Default Session").last().click();

  await page.getByText("timestamp", { exact: true }).last().isVisible();
  await page.getByText("text", { exact: true }).last().isVisible();
  await page.getByText("sender", { exact: true }).last().isVisible();
  await page.getByText("sender_name", { exact: true }).last().isVisible();
  await page.getByText("session_id", { exact: true }).last().isVisible();
  await page.getByText("files", { exact: true }).last().isVisible();

  await page.getByRole("gridcell").last().isVisible();
  await page.getByTestId("icon-Trash2").first().click();
  await page.getByPlaceholder("Send a message...").last().isVisible();
});

test("Document QA", async ({ page }) => {
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

  await page.getByRole("heading", { name: "Document QA" }).click();
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
    .getByTestId("popover-anchor-input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByTestId("icon-FileSearch2").click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(path.join(__dirname, "/assets/test_file.txt"));
  await page.getByText("test_file.txt").isVisible();

  await page.waitForTimeout(2000);

  await page.getByTestId("button_run_chat output").click();
  await page.getByText("built successfully").last().click({
    timeout: 15000,
  });

  await page.getByText("Playground", { exact: true }).click();
  await page
    .getByText("No input message provided.", { exact: true })
    .last()
    .isVisible();

  await page
    .getByPlaceholder("Send a message...")
    .last()
    .fill("whats the text in the file?");
  await page.getByTestId("icon-LucideSend").last().click();

  await page.waitForTimeout(3000);

  await page.getByText("this is a test file").last().isVisible();

  await page.getByText("Default Session").last().click();

  await page.getByText("timestamp", { exact: true }).last().isVisible();
  await page.getByText("text", { exact: true }).last().isVisible();
  await page.getByText("sender", { exact: true }).last().isVisible();
  await page.getByText("sender_name", { exact: true }).last().isVisible();
  await page.getByText("session_id", { exact: true }).last().isVisible();
  await page.getByText("files", { exact: true }).last().isVisible();

  await page.getByRole("gridcell").last().isVisible();
  await page.getByTestId("icon-Trash2").first().click();
  await page.getByPlaceholder("Send a message...").last().isVisible();
});

test("Blog Writer", async ({ page }) => {
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

  await page.getByRole("heading", { name: "Blog Writer" }).click();
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
    .getByTestId("popover-anchor-input-openai_api_key")
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page
    .getByTestId("input-list-input_urls-0")
    .nth(0)
    .fill(
      "https://www.natgeokids.com/uk/discover/animals/sea-life/turtle-facts/",
    );
  await page
    .getByTestId("input-list-input_urls-1")
    .nth(0)
    .fill("https://www.originaldiving.com/blog/top-ten-turtle-facts");

  await page
    .getByTestId("popover-anchor-input-input_value")
    .nth(0)
    .fill(
      "Use the references above for style to write a new blog/tutorial about turtles. Suggest non-covered topics.",
    );

  await page.getByTestId("button_run_chat output").click();
  await page.waitForTimeout(5000);
  await page.getByText("built successfully").last().click({
    timeout: 30000,
  });

  await page.getByText("Playground", { exact: true }).click();
  await page
    .getByPlaceholder(
      "No chat input variables found. Click to run your flow.",
      { exact: true },
    )
    .last()
    .isVisible();

  await page.waitForTimeout(3000);

  await page.getByText("turtles").last().isVisible();
  await page.getByText("sea").last().isVisible();
  await page.getByText("survival").last().isVisible();

  await page.getByText("Instructions").last().click();

  const value = await page
    .getByPlaceholder("Enter text...")
    .last()
    .inputValue();

  expect(value).toBe(
    "Use the references above for style to write a new blog/tutorial about turtles. Suggest non-covered topics.",
  );

  await page.getByTestId("icon-ExternalLink").last().click();

  const count = await page
    .getByText(
      "Use the references above for style to write a new blog/tutorial about turtles. Suggest non-covered topics.",
    )
    .count();

  if (count <= 1) {
    expect(false).toBe(true);
  }
});

test("Vector Store RAG", async ({ page }) => {
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

  await page.getByRole("heading", { name: "Vector Store RAG" }).click();
  await page.waitForTimeout(1000);

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  if (
    !process.env.OPENAI_API_KEY ||
    !process.env.ASTRA_DB_API_ENDPOINT ||
    !process.env.ASTRA_DB_APPLICATION_TOKEN
  ) {
    //You must set the OPENAI_API_KEY, ASTRA_DB_API_ENDPOINT and ASTRA_DB_APPLICATION_TOKEN on .env file to run this test
    expect(false).toBe(true);
  }

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .nth(0)
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .nth(1)
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .nth(2)
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page
    .getByTestId("popover-anchor-input-token")
    .nth(0)
    .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");
  await page
    .getByTestId("popover-anchor-input-token")
    .nth(1)
    .fill(process.env.ASTRA_DB_APPLICATION_TOKEN ?? "");

  await page
    .getByTestId("popover-anchor-input-api_endpoint")
    .nth(0)
    .fill(process.env.ASTRA_DB_API_ENDPOINT ?? "");
  await page
    .getByTestId("popover-anchor-input-api_endpoint")
    .nth(1)
    .fill(process.env.ASTRA_DB_API_ENDPOINT ?? "");

  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByTestId("icon-FileSearch2").last().click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(path.join(__dirname, "/assets/test_file.txt"));
  await page.getByText("test_file.txt").isVisible();
  await page.waitForTimeout(2000);

  await page.getByTestId("button_run_astra db").first().click();
  await page.getByText("built successfully").last().click({
    timeout: 30000,
  });

  await page.getByTestId("button_run_chat output").click();
  await page.getByText("built successfully").last().click({
    timeout: 30000,
  });

  await page.getByText("Playground", { exact: true }).click();

  await page.getByPlaceholder("Send a message...").last().fill("hello");

  await page.getByTestId("icon-LucideSend").last().click();

  await page
    .getByText("This is a test file.", { exact: true })
    .last()
    .isVisible();

  await page.getByText("Memories", { exact: true }).last().click();
  await page.getByText("Default Session").last().click();

  await page.getByText("timestamp", { exact: true }).last().isVisible();
  await page.getByText("text", { exact: true }).last().isVisible();
  await page.getByText("sender", { exact: true }).last().isVisible();
  await page.getByText("sender_name", { exact: true }).last().isVisible();
  await page.getByText("session_id", { exact: true }).last().isVisible();
  await page.getByText("files", { exact: true }).last().isVisible();

  await page.getByRole("gridcell").last().isVisible();
  await page.getByTestId("icon-Trash2").first().click();
  await page.getByPlaceholder("Send a message...").last().isVisible();
});
