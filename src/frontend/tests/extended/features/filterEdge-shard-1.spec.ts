import { expect, test } from "@playwright/test";

test("user must see on handle click the possibility connections - RetrievalQA", async ({
  page,
}) => {
  await page.goto("/");
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await page.waitForSelector('[id="new-project-btn"]', {
    timeout: 30000,
  });

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
  await page.getByPlaceholder("Search").fill("retrievalqa");

  await page.waitForTimeout(1000);
  await page
    .getByTestId("chainsRetrieval QA")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.waitForTimeout(500);

  let visibleElementHandle;

  const outputElements = await page
    .getByTestId("handle-retrievalqa-shownode-text-right")
    .all();

  for (const element of outputElements) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.click({
    force: true,
  });

  const disclosureTestIds = [
    "disclosure-inputs",
    "disclosure-outputs",
    "disclosure-data",
    "disclosure-models",
    "disclosure-helpers",
    "disclosure-vector stores",
    "disclosure-embeddings",
    "disclosure-agents",
    "disclosure-chains",
    "disclosure-memories",
    "disclosure-prototypes",
    "disclosure-retrievers",
    "disclosure-text splitters",
  ];

  const elementTestIds = [
    "inputsChat Input",
    "outputsChat Output",
    "dataAPI Request",
    "modelsAmazon Bedrock",
    "helpersChat Memory",
    "vectorstoresAstra DB",
    "embeddingsAmazon Bedrock Embeddings",
    "agentsTool Calling Agent",
    "chainsConversationChain",
    "memoriesAstra DB Chat Memory",
    "prototypesConditional Router",
    "retrieversSelf Query Retriever",
    "textsplittersCharacterTextSplitter",
  ];

  await Promise.all(
    disclosureTestIds.map((id) => expect(page.getByTestId(id)).toBeVisible()),
  );

  await Promise.all(
    elementTestIds.map((id) =>
      expect(page.getByTestId(id).first()).toBeVisible(),
    ),
  );

  await page.getByPlaceholder("Search").click();

  const notVisibleModelSpecsTestIds = [
    "model_specsVertexAI",
    "model_specsCTransformers",
    "model_specsAmazon Bedrock",
    "modelsAzure OpenAI",
    "model_specsAzureChatOpenAI",
    "model_specsChatAnthropic",
    "model_specsChatLiteLLM",
    "model_specsChatOllama",
    "model_specsChatOpenAI",
    "model_specsChatVertexAI",
  ];

  await Promise.all(
    notVisibleModelSpecsTestIds.map((id) =>
      expect(page.getByTestId(id)).not.toBeVisible(),
    ),
  );

  const chainInputElements1 = await page
    .getByTestId("handle-retrievalqa-shownode-llm-left")
    .all();

  for (const element of chainInputElements1) {
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

  const rqaChainInputElements0 = await page
    .getByTestId("handle-retrievalqa-shownode-template-left")
    .all();

  for (const element of rqaChainInputElements0) {
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
