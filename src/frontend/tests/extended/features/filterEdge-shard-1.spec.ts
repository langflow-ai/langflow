import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must see on handle click the possibility connections - RetrievalQA",
  { tag: ["@release", "@api", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="sidebar-options-trigger"]', {
      timeout: 3000,
    });

    await addLegacyComponents(page);

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
      "disclosure-input / output",
      "disclosure-data",
      "disclosure-models",
      "disclosure-helpers",
      "disclosure-agents",
      "disclosure-logic",
      "disclosure-tools",
      "disclosure-bundles-langchain",
      "disclosure-bundles-assemblyai",
      "disclosure-bundles-datastax",
    ];

    const elementTestIds = [
      "input_outputChat Output",
      "dataAPI Request",
      "langchain_utilitiesTool Calling Agent",
      "langchain_utilitiesConversationChain",
      "mem0Mem0 Chat Memory",
      "logicCondition",
      "langchain_utilitiesSelf Query Retriever",
      "langchain_utilitiesCharacter Text Splitter",
    ];

    await Promise.all(
      disclosureTestIds.map((id) => {
        if (!expect(page.getByTestId(id)).toBeVisible()) {
          console.error(`${id} is not visible`);
        }
        return expect(page.getByTestId(id)).toBeVisible();
      }),
    );

    await Promise.all(
      elementTestIds.map(async (id) => {
        if (!expect(page.getByTestId(id).first()).toBeVisible()) {
          console.error(`${id} is not visible`);
        }
        return expect(page.getByTestId(id).first()).toBeVisible();
      }),
    );

    await page.getByTestId("sidebar-search-input").click();

    const visibleModelSpecsTestIds = [
      "cohereCohere Language Models",
      "groqGroq",
      "lmstudioLM Studio",
      "maritalkMariTalk",
      "perplexityPerplexity",
      "baiduQianfan",
      "sambanovaSambaNova",
      "xaixAI",
    ];

    await Promise.all(
      visibleModelSpecsTestIds.map((id) => {
        if (!expect(page.getByTestId(id)).toBeVisible()) {
          console.error(`${id} is not visible`);
        }
        return expect(page.getByTestId(id)).toBeVisible();
      }),
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
    await expect(page.getByTestId("disclosure-logic")).toBeVisible();
  },
);
