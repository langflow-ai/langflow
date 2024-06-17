import { expect, test } from "@playwright/test";

test("should exists Store", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").isVisible();
  await page.getByTestId("button-store").isEnabled();
});

test("should not have an API key", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(2000);

  await page.getByText("API Key Error").isVisible();
});

test("should find a searched Component on Store", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("search-store-input").fill("File Loader");
  await page.getByTestId("search-store-button").click();
  await page.getByText("File Loader").isVisible();

  await page.getByTestId("search-store-input").fill("Basic RAG");
  await page.getByTestId("search-store-button").click();
  await page.getByText("Basic RAG").isVisible();

  await page.getByTestId("search-store-input").fill("YouTube QA");
  await page.getByTestId("search-store-button").click();
  await page.getByText("YouTube QA").isVisible();
});

test("should filter by tag", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("tag-selector-Agent").click();
  await page.getByText("File Loader").isVisible();
  await page.getByTestId("tag-selector-Agent").click();
  await page.getByText("Album Cover Builder").isVisible();

  await page.getByTestId("tag-selector-Memory").click();
  await page.getByText("MP3 QA12").isVisible();

  await page.getByTestId("tag-selector-Chain").click();
  await page.getByText("There are no").isVisible();
  await page.getByTestId("tag-selector-Chain").click();

  await page.getByTestId("tag-selector-Vector Store").click();
  await page.getByText("MP3 QA12").isVisible();
  await page.getByTestId("tag-selector-Vector Store").click();
  await page.getByTestId("tag-selector-Memory").click();

  await page.getByText("Basic RAG").isVisible();
});

test("should order the visualization", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByText("Basic RAG").isVisible();

  await page.getByTestId("select-order-store").click();
  await page.waitForTimeout(2000);
  await page.getByText("Alphabetical").click();

  await page.getByText("Album Cover Builder").isVisible();

  await page.getByTestId("select-order-store").click();
  await page.getByText("Popular").click();

  await page.getByText("Basic RAG").isVisible();
});

test("should filter by type", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByText("Website Content QA").isVisible();

  await page.getByTestId("flows-button-store").click();
  await page.waitForTimeout(8000);

  let iconGroup = await page.getByTestId("icon-Group")?.count();
  expect(iconGroup).not.toBe(0);

  await page.getByText("icon-ToyBrick").last().isHidden();

  await page.getByTestId("components-button-store").click();
  await page.waitForTimeout(8000);

  await page.getByTestId("icon-Group").last().isHidden();
  let toyBrick = await page.getByTestId("icon-ToyBrick")?.count();
  expect(toyBrick).not.toBe(0);

  await page.getByTestId("all-button-store").click();
  await page.waitForTimeout(8000);

  let iconGroupAllCount = await page.getByTestId("icon-Group")?.count();
  await page.waitForTimeout(2000);
  let toyBrickAllCount = await page.getByTestId("icon-ToyBrick")?.count();
  await page.waitForTimeout(2000);

  if (iconGroupAllCount === 0 || toyBrickAllCount === 0) {
    expect(false).toBe(true);
  }
});

test("should add API-KEY", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("api-key-button-store").click();
  await page
    .getByPlaceholder("Insert your API Key")
    .fill("testtesttesttesttesttest");

  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.waitForTimeout(2000);
  await page.getByText("API Key Error").isVisible();

  await page
    .getByPlaceholder("Insert your API Key")
    .fill(process.env.STORE_API_KEY ?? "");
  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.waitForTimeout(2000);
  await page.getByText("API Key Error").isHidden();
});

test("should like and add components and flows", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(1000);

  await page.getByTestId("api-key-button-store").click();

  await page
    .getByPlaceholder("Insert your API Key")
    .fill(process.env.STORE_API_KEY ?? "");
  await page.getByTestId("api-key-save-button-store").click();

  await page.waitForTimeout(2000);
  await page.getByText("Success! Your API Key has been saved.").isVisible();

  await page.waitForTimeout(2000);
  await page.getByText("API Key Error").isHidden();

  await page.waitForTimeout(2000);

  await page.getByTestId("button-store").click();
  await page.waitForTimeout(5000);

  const likedValue = await page
    .getByTestId("likes-Website Content QA")
    .innerText();

  await page.getByTestId("like-Website Content QA").click();

  await page.waitForTimeout(5000);
  const likedValueAfter = await page
    .getByTestId("likes-Website Content QA")
    .innerText();

  if (Number(likedValue) === Number(likedValueAfter)) {
    expect(false).toBe(true);
  }

  const downloadValue = await page
    .getByTestId("downloads-Website Content QA")
    .innerText();

  await page.getByTestId("install-Website Content QA").click();
  await page.waitForTimeout(2000);
  await page.getByText("Flow Installed Successfully").isVisible();
  await page.waitForTimeout(5000);

  const downloadValueAfter = await page
    .getByTestId("downloads-Website Content QA")
    .innerText();

  if (Number(downloadValue) === Number(downloadValueAfter)) {
    expect(false).toBe(true);
  }

  await page.getByTestId("install-Basic RAG").click();
  await page.waitForTimeout(2000);
  await page.getByText("Component Installed Successfully").isVisible();
  await page.waitForTimeout(5000);

  await page.getByText("My Collection").click();
  await page.getByText("Website Content QA").first().isVisible();

  await page.getByText("Components").first().click();
  await page.getByText("Basic RAG").first().isVisible();
});

test("should share component with share button", async ({ page }) => {
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
  await page.waitForTimeout(1000);
  const flowName = await page.getByTestId("flow_name").innerText();
  await page.getByTestId("flow_name").click();
  await page.getByText("Settings").click();
  const flowDescription = await page
    .getByPlaceholder("Flow description")
    .inputValue();
  await page.getByText("Save").last().click();
  await page.getByText("Close").last().click();

  await page.getByTestId("icon-Share3").first().click();
  await page.getByText("Name:").isVisible();
  await page.getByText("Description:").isVisible();
  await page.getByText("Set workflow status to public").isVisible();
  await page
    .getByText(
      "Attention: API keys in specified fields are automatically removed upon sharing.",
    )
    .isVisible();
  await page.getByText("Export").first().isVisible();
  await page.getByText("Share Flow").first().isVisible();

  await page.waitForTimeout(5000);

  await page.getByText("Agent").first().isVisible();
  await page.getByText("Memory").first().isVisible();
  await page.getByText("Chain").first().isVisible();
  await page.getByText("Vector Store").first().isVisible();
  await page.getByText("Prompt").last().isVisible();
  await page.getByTestId("public-checkbox").isChecked();
  await page.getByText(flowName).last().isVisible();
  await page.getByText(flowDescription).last().isVisible();
  await page.waitForTimeout(1000);
  await page.getByText("Flow shared successfully").last().isVisible();
});
