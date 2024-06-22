import { expect, test } from "@playwright/test";

test("LLMChain - Tooltip", async ({ page }) => {
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
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(3000);

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("llmchain");

  await page.waitForTimeout(1000);
  await page
    .getByTestId("chainsLLMChain")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[7]/button/div[1]',
    )
    .hover()
    .then(async () => {
      await expect(page.getByTestId("tooltip-Chains").first()).toBeVisible();
      await expect(
        page.getByTestId("tooltip-Model Specs").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("tooltip-Vector Search").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("tooltip-Text Splitters").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("tooltip-Retrievers").first(),
      ).toBeVisible();
      await expect(page.getByTestId("tooltip-Tools").first()).toBeVisible();
      await expect(page.getByTestId("tooltip-Memories").first()).toBeVisible();
      await expect(page.getByTestId("tooltip-Agents").first()).toBeVisible();
      await expect(page.getByTestId("tooltip-Helpers").first()).toBeVisible();
      await expect(page.getByTestId("tooltip-Utilities").first()).toBeVisible();
      await page.getByTestId("icon-X").click();
      await page.waitForTimeout(500);
    });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[4]/div/button/div[1]',
    )
    .hover()
    .then(async () => {
      await expect(
        page.getByTestId("tooltip-Model Specs").first(),
      ).toBeVisible();
      await page.waitForTimeout(2000);

      await expect(page.getByTestId("tooltip-Models").first()).toBeVisible();

      await page.getByTestId("icon-Search").click();

      await page.waitForTimeout(500);
    });
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div/div/div[2]/div/div/div[2]/div[3]/div/button/div[1]',
    )
    .hover()
    .then(async () => {
      await page.waitForTimeout(2000);

      await expect(page.getByTestId("tooltip-Chains").first()).toBeVisible();
      await expect(
        page.getByTestId("tooltip-Experimental").first(),
      ).toBeVisible();
      await expect(page.getByTestId("tooltip-Agents").first()).toBeVisible();
      await expect(page.getByTestId("tooltip-Helpers").first()).toBeVisible();

      await page.waitForTimeout(500);
    });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[5]/div/button/div[1]',
    )
    .hover()
    .then(async () => {
      await expect(
        page.getByTestId("empty-tooltip-filter").first(),
      ).toBeVisible();
    });
});

test("LLMChain - Filter", async ({ page }) => {
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

  await page.getByTestId(
    "input-list-plus-btn-edit_metadata_indexing_include-2",
  );

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(3000);
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("llmchain");

  await page.waitForTimeout(1000);
  await page
    .getByTestId("chainsLLMChain")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.waitForTimeout(500);

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[7]/button/div[1]',
    )
    .click();

  await expect(page.getByTestId("disclosure-model specs")).toBeVisible();
  await expect(page.getByTestId("model_specsAnthropic").first()).toBeVisible();
  await expect(page.getByTestId("model_specsAmazon Bedrock")).toBeVisible();
  await expect(page.getByTestId("model_specsAzureChatOpenAI")).toBeVisible();
  await expect(page.getByTestId("model_specsChatLiteLLM")).toBeVisible();
  await expect(page.getByTestId("model_specsChatOllama")).toBeVisible();
  await expect(page.getByTestId("model_specsChatOpenAI")).toBeVisible();
  await expect(page.getByTestId("model_specsChatVertexAI")).toBeVisible();
  await expect(
    page.getByTestId("model_specsGoogle Generative AI"),
  ).toBeVisible();
  await expect(
    page.getByTestId("model_specsHugging Face Inference API"),
  ).toBeVisible();
  await expect(page.getByTestId("model_specsOllama")).toBeVisible();
  await expect(
    page.getByTestId("model_specsQianfanChatEndpoint"),
  ).toBeVisible();
  await expect(page.getByTestId("model_specsQianfanLLMEndpoint")).toBeVisible();
  await expect(page.getByTestId("model_specsVertexAI")).toBeVisible();

  await page.getByPlaceholder("Search").click();

  await expect(page.getByTestId("model_specsVertexAI")).not.toBeVisible();
  await expect(page.getByTestId("model_specsCTransformers")).not.toBeVisible();
  await expect(page.getByTestId("model_specsAmazon Bedrock")).not.toBeVisible();
  await expect(page.getByTestId("modelsAzure OpenAI")).not.toBeVisible();
  await expect(
    page.getByTestId("model_specsAzureChatOpenAI"),
  ).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatAnthropic")).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatLiteLLM")).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatOllama")).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatOpenAI")).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatVertexAI")).not.toBeVisible();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[4]/div/button/div[1]',
    )
    .click();

  await expect(page.getByTestId("disclosure-models")).toBeVisible();
  await expect(page.getByTestId("disclosure-model specs")).toBeVisible();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[3]/div/button/div[1]',
    )
    .click();

  await expect(page.getByTestId("disclosure-saved")).toBeVisible();

  await expect(page.getByTestId("disclosure-helpers")).toBeVisible();
  await expect(page.getByTestId("disclosure-agents")).toBeVisible();
  await expect(page.getByTestId("disclosure-chains")).toBeVisible();
  await expect(page.getByTestId("disclosure-experimental")).toBeVisible();
});
