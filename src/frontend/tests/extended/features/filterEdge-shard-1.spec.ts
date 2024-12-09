import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must see on handle click the possibility connections - RetrievalQA",
  { tag: ["@release", "@api", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="sidebar-options-trigger"]', {
      timeout: 3000,
    });

    await page.getByTestId("sidebar-options-trigger").click();

    await expect(page.getByTestId("sidebar-legacy-switch")).toBeVisible({
      timeout: 5000,
    });
    await page.getByTestId("sidebar-legacy-switch").click();
    await expect(page.getByTestId("sidebar-legacy-switch")).toBeChecked();
    await page.getByTestId("sidebar-options-trigger").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("retrievalqa");

    await page.waitForSelector(
      '[data-testid="langchain_utilitiesRetrieval QA"]',
      {
        timeout: 3000,
      },
    );
    await page
      .getByTestId("langchain_utilitiesRetrieval QA")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await adjustScreenView(page);
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
      "disclosure-memories",
      "disclosure-logic",
      "disclosure-tools",
      "disclosure-bundles-langchain",
      "disclosure-bundles-assemblyai",
      "disclosure-bundles-datastax",
    ];

    const elementTestIds = [
      "inputsChat Input",
      "outputsChat Output",
      "dataAPI Request",
      "modelsAmazon Bedrock",
      "helpersMessage History",
      "vectorstoresAstra DB",
      "embeddingsAmazon Bedrock Embeddings",
      "langchain_utilitiesTool Calling Agent",
      "langchain_utilitiesConversationChain",
      "memoriesAstra DB Chat Memory",
      "logicCondition",
      "langchain_utilitiesSelf Query Retriever",
      "langchain_utilitiesCharacterTextSplitter",
    ];

    await Promise.all(
      disclosureTestIds.map((id) => expect(page.getByTestId(id)).toBeVisible()),
    );

    await Promise.all(
      elementTestIds.map((id) =>
        expect(page.getByTestId(id).first()).toBeVisible(),
      ),
    );

    await page.getByTestId("sidebar-search-input").click();

    const visibleModelSpecsTestIds = [
      "modelsAIML",
      "modelsAmazon Bedrock",
      "modelsAnthropic",
      "modelsAzure OpenAI",
      "modelsCohere",
      "modelsGoogle Generative AI",
      "modelsGroq",
      "modelsHuggingFace",
      "modelsLM Studio",
      "modelsMaritalk",
      "modelsMistralAI",
      "modelsNVIDIA",
      "modelsOllama",
      "modelsOpenAI",
      "modelsPerplexity",
      "modelsQianfan",
      "modelsSambaNova",
      "modelsVertex AI",
    ];

    await Promise.all(
      visibleModelSpecsTestIds.map((id) =>
        expect(page.getByTestId(id)).toBeVisible(),
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
    await expect(page.getByTestId("disclosure-memories")).toBeVisible();
    await expect(page.getByTestId("disclosure-logic")).toBeVisible();
  },
);
