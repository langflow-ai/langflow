import { expect, test } from "@playwright/test";
test.beforeEach(async ({ page }) => {
  await page.waitForTimeout(23000);
  test.setTimeout(120000);
});
test("LLMChain - Tooltip", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(1000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(1000);

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(1000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("llmchain");

  await page.waitForTimeout(1000);
  await page
    .getByTestId("chainsLLMChain")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div/div/div[2]/div/div/div[2]/div[3]/div/button/div/div'
    )
    .hover()
    .then(async () => {
      await expect(
        page.getByTestId("available-input-model_specs").first()
      ).toBeVisible();

      await expect(page.getByTestId("tooltip-Models").first()).toBeVisible();

      await expect(
        page.getByTestId("tooltip-AzureOpenAIModel").first()
      ).toBeVisible();

      await expect(
        page.getByTestId("tooltip-Model Specs").first()
      ).toBeVisible();

      await page.getByTestId("icon-X").click();
      await page.waitForTimeout(500);
    });

  await page.getByTitle("fit view").click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div/div/div[2]/div/div/div[2]/div[4]/div/button/div/div'
    )
    .hover()
    .then(async () => {
      await expect(
        page.getByTestId("available-input-memories").first()
      ).toBeVisible();

      await expect(page.getByTestId("tooltip-Memories").first()).toBeVisible();

      await expect(
        page
          .getByTestId(
            "tooltip-ConversationBufferMemory, ConversationBufferWindowMemory, ConversationEntityMemory, ConversationKGMemory, ConversationSummaryMemory, MotorheadMemory, VectorStoreRetrieverMemory"
          )
          .first()
      ).toBeVisible();
      await page.getByTestId("icon-Search").click();

      await page.waitForTimeout(500);
    });
  await page.getByTitle("fit view").click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div/div/div[2]/div/div/div[2]/div[5]/div/button/div/div'
    )
    .hover()
    .then(async () => {
      await expect(
        page.getByTestId("empty-tooltip-filter").first()
      ).toBeVisible();
    });
});

test("LLMChain - Filter", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(1000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(1000);

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(1000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("llmchain");

  await page.waitForTimeout(1000);
  await page
    .getByTestId("chainsLLMChain")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click();

  await page.waitForTimeout(500);

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div/div/div[2]/div/div/div[2]/div[3]/div/button/div/div'
    )
    .click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div/div/div[2]/div/div/div[2]/div[3]/div/button/div/div'
    )
    .click();
  await page.getByTestId("icon-Search").click();

  await expect(page.getByTestId("disclosure-models")).toBeVisible();
  await expect(page.getByTestId("disclosure-model specs")).toBeVisible();

  await expect(page.getByTestId("modelsAzureOpenAI")).toBeVisible();
  await expect(page.getByTestId("model_specsAmazon Bedrock")).toBeVisible();
  await expect(page.getByTestId("model_specsAnthropic")).toBeVisible();
  await expect(page.getByTestId("model_specsAnthropicLLM")).toBeVisible();
  await expect(page.getByTestId("model_specsAzureChatOpenAI")).toBeVisible();
  await expect(page.getByTestId("model_specsChatAnthropic")).toBeVisible();
  await expect(page.getByTestId("model_specsChatLiteLLM")).toBeVisible();
  await expect(page.getByTestId("model_specsChatOllama")).toBeVisible();
  await expect(page.getByTestId("model_specsChatOpenAI")).toBeVisible();
  await expect(page.getByTestId("model_specsChatVertexAI")).toBeVisible();
  await expect(page.getByTestId("model_specsCohere")).toBeVisible();
  await expect(page.getByTestId("model_specsCTransformers")).toBeVisible();
  await expect(
    page.getByTestId("model_specsGoogle Generative AI")
  ).toBeVisible();
  await expect(
    page.getByTestId("model_specsHugging Face Inference API")
  ).toBeVisible();
  await expect(page.getByTestId("model_specsLlamaCpp")).toBeVisible();
  await expect(page.getByTestId("model_specsOllama")).toBeVisible();
  await expect(
    page.getByTestId("model_specsQianfanChatEndpoint")
  ).toBeVisible();
  await expect(page.getByTestId("model_specsQianfanLLMEndpoint")).toBeVisible();
  await expect(page.getByTestId("model_specsVertexAI")).toBeVisible();

  await page.getByPlaceholder("Search").click();

  await expect(page.getByTestId("model_specsVertexAI")).not.toBeVisible();
  await expect(page.getByTestId("model_specsCTransformers")).not.toBeVisible();
  await expect(page.getByTestId("model_specsAmazon Bedrock")).not.toBeVisible();
  await expect(page.getByTestId("modelsAzureOpenAI")).not.toBeVisible();
  await expect(page.getByTestId("model_specsAnthropic")).not.toBeVisible();
  await expect(page.getByTestId("model_specsAnthropicLLM")).not.toBeVisible();
  await expect(
    page.getByTestId("model_specsAzureChatOpenAI")
  ).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatAnthropic")).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatLiteLLM")).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatOllama")).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatOpenAI")).not.toBeVisible();
  await expect(page.getByTestId("model_specsChatVertexAI")).not.toBeVisible();
  await expect(page.getByTestId("model_specsCohere")).not.toBeVisible();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div/div/div[2]/div/div/div[2]/div[4]/div/button/div/div'
    )
    .click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div[1]/div[1]/div/div/div[2]/div/div/div[2]/div[4]/div/button/div/div'
    )
    .click();

  await expect(page.getByTestId("disclosure-memories")).toBeVisible();
  await expect(
    page.getByTestId("memoriesConversationBufferMemory")
  ).toBeVisible();
  await expect(
    page.getByTestId("memoriesConversationBufferWindowMemory")
  ).toBeVisible();
  await expect(
    page.getByTestId("memoriesConversationEntityMemory")
  ).toBeVisible();
  await expect(page.getByTestId("memoriesConversationKGMemory")).toBeVisible();
  await expect(page.getByTestId("memoriesConversationKGMemory")).toBeVisible();
  await expect(
    page.getByTestId("memoriesConversationSummaryMemory")
  ).toBeVisible();
  await expect(
    page.getByTestId("memoriesVectorStoreRetrieverMemory")
  ).toBeVisible();

  await page.getByTestId("rf__wrapper").click();

  await expect(
    page.getByTestId("memoriesConversationBufferMemory")
  ).not.toBeVisible();
  await expect(
    page.getByTestId("memoriesConversationBufferWindowMemory")
  ).not.toBeVisible();
  await expect(
    page.getByTestId("memoriesConversationEntityMemory")
  ).not.toBeVisible();
  await expect(
    page.getByTestId("memoriesConversationKGMemory")
  ).not.toBeVisible();
  await expect(
    page.getByTestId("memoriesConversationKGMemory")
  ).not.toBeVisible();
  await expect(
    page.getByTestId("memoriesConversationSummaryMemory")
  ).not.toBeVisible();
  await expect(
    page.getByTestId("memoriesVectorStoreRetrieverMemory")
  ).not.toBeVisible();
});
