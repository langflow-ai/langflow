import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";

test(
  "user must see on handle click the possibility connections - RetrievalQA",
  { tag: ["@release", "@api", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await page.waitForSelector('[data-testid="sidebar-options-trigger"]', {
      timeout: 3000,
    });

    await addLegacyComponents(page);

    await addComponentFromSidebar(page, {
      search: "retrievalqa",
      testId: "langchain_utilitiesRetrieval QA",
      position: { x: 200, y: 200 },
    });

    await adjustScreenView(page);

    const outputHandle = page
      .getByTestId("handle-retrievalqa-shownode-text-right")
      .first();
    await expect(outputHandle).toBeVisible();
    await outputHandle.click({ position: { x: 31, y: 16 } });

    const disclosureTestIds = [
      "disclosure-input & output",
      "disclosure-data sources",
      "disclosure-models & agents",
      "disclosure-llm operations",
      "disclosure-files & knowledge",
      "disclosure-processing",
      "disclosure-flow control",
      "disclosure-utilities",
    ];

    const elementTestIds = [
      "input_outputChat Output",
      "data_sourceAPI Request",
      "langchain_utilitiesTool Calling Agent",
      "langchain_utilitiesConversationChain",
      "flow_controlsCondition",
      "langchain_utilitiesSelf Query Retriever",
      "langchain_utilitiesCharacter Text Splitter",
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

    const visibleModelSpecsTestIds = ["cohereCohere Language Models"];

    await Promise.all(
      visibleModelSpecsTestIds.map((id) =>
        expect(page.getByTestId(id)).toBeVisible(),
      ),
    );

    const modelHandle = page
      .getByTestId("handle-retrievalqa-shownode-language model-left")
      .first();
    await expect(modelHandle).toBeVisible();
    await modelHandle.click({ position: { x: 1, y: 16 } });

    await expect(page.getByTestId("disclosure-models & agents")).toBeVisible();

    await outputHandle.click({ position: { x: 31, y: 16 } });

    await expect(page.getByTestId("disclosure-input & output")).toBeVisible();
    await expect(page.getByTestId("disclosure-data sources")).toBeVisible();
    await expect(page.getByTestId("disclosure-models & agents")).toBeVisible();
  },
);
