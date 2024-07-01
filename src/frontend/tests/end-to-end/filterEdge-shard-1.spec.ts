import { expect, test } from "@playwright/test";

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
  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });
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

  let visibleElementHandle;

  const llmChainOutputElements = await page
    .getByTestId("handle-llmchain-shownode-text-right")
    .all();

  for (const element of llmChainOutputElements) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.click({
    force: true,
  });

  await expect(page.getByTestId("disclosure-helpers")).toBeVisible();
  await expect(page.getByTestId("disclosure-agents")).toBeVisible();
  await expect(page.getByTestId("disclosure-chains")).toBeVisible();
  await expect(page.getByTestId("disclosure-utilities")).toBeVisible();
  await expect(page.getByTestId("disclosure-memories")).toBeVisible();
  await expect(page.getByTestId("disclosure-prototypes")).toBeVisible();
  await expect(page.getByTestId("disclosure-retrievers")).toBeVisible();
  await expect(page.getByTestId("disclosure-text splitters")).toBeVisible();
  await expect(page.getByTestId("disclosure-toolkits")).toBeVisible();
  await expect(page.getByTestId("disclosure-tools")).toBeVisible();

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

  const llmChainInputElements1 = await page
    .getByTestId("handle-llmchain-shownode-llm-left")
    .all();

  for (const element of llmChainInputElements1) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.blur();

  await visibleElementHandle.click({
    force: true,
  });

  await expect(page.getByTestId("disclosure-models")).toBeVisible();

  const llmChainInputElements0 = await page
    .getByTestId("handle-llmchain-shownode-template-left")
    .all();

  for (const element of llmChainInputElements0) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.click();

  await expect(page.getByTestId("disclosure-helpers")).toBeVisible();
  await expect(page.getByTestId("disclosure-agents")).toBeVisible();
  await expect(page.getByTestId("disclosure-chains")).toBeVisible();
  await expect(page.getByTestId("disclosure-prototypes")).toBeVisible();
});
