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
      await expect(
        page.getByTestId("available-output-chains").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-textsplitters").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-retrievers").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-prototypes").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-tools").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-memories").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-toolkits").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-chains").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-agents").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-helpers").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-output-langchain_utilities").first(),
      ).toBeVisible();

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
        page.getByTestId("available-input-models").first(),
      ).toBeVisible();
      await page.waitForTimeout(2000);

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

      await expect(
        page.getByTestId("available-input-chains").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-input-prototypes").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-input-agents").first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("available-input-helpers").first(),
      ).toBeVisible();

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

  await expect(page.getByTestId("disclosure-models")).toBeVisible();
  await expect(
    page.getByTestId("modelsGoogle Generative AI").first(),
  ).toBeVisible();
  await expect(page.getByTestId("chainsLLMChain").first()).toBeVisible();
  await expect(
    page.getByTestId("langchain_utilitiesSearchApi").first(),
  ).toBeVisible();
  await expect(
    page.getByTestId("memoriesAstra DB Message Reader").first(),
  ).toBeVisible();
  await expect(
    page.getByTestId("prototypesFlow as Tool").first(),
  ).toBeVisible();
  await expect(
    page.getByTestId("retrieversAmazon Kendra Retriever").first(),
  ).toBeVisible();
  await expect(
    page.getByTestId("textsplittersCharacterTextSplitter").first(),
  ).toBeVisible();
  await expect(
    page.getByTestId("toolkitsVectorStoreInfo").first(),
  ).toBeVisible();
  await expect(page.getByTestId("toolsSearchApi").first()).toBeVisible();

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

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[3]/div/button/div[1]',
    )
    .click();

  await expect(page.getByTestId("disclosure-helpers")).toBeVisible();
  await expect(page.getByTestId("disclosure-agents")).toBeVisible();
  await expect(page.getByTestId("disclosure-chains")).toBeVisible();
  await expect(page.getByTestId("disclosure-prototypes")).toBeVisible();
});
