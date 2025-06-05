import { expect, test } from "@playwright/test";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { updateOldComponents } from "../../utils/update-old-components";
import { zoomOut } from "../../utils/zoom-out";

test(
  "user must be able to check similarity between embedding texts",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();

    await addLegacyComponents(page);

    //first component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("openai embedding");
    await page.waitForSelector("text=OpenAI Embeddings", {
      timeout: 1000,
    });

    await page
      .getByText("OpenAI Embeddings", { exact: true })
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 0, y: 0 },
      });

    await zoomOut(page, 5);

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text embedder");
    await page.waitForSelector("text=Text Embedder", {
      timeout: 1000,
    });

    await page
      .getByTestId("embeddingsText Embedder")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 100, y: 400 },
      });

    //fourth component

    await page
      .getByTestId("embeddingsText Embedder")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 400 },
      });

    //fifth component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("embedding similarity");
    await page.waitForSelector("text=Embedding Similarity", {
      timeout: 1000,
    });

    await page
      .getByTestId("embeddingsEmbedding Similarity")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 350, y: 100 },
      });

    //sisxth component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("data to message");
    await page.waitForSelector("text=Data to Message", {
      timeout: 1000,
    });

    await page
      .getByTestId("processingData to Message")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 100 },
      });

    //seventh component

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("text output");
    await page.waitForSelector("text=Text Output", {
      timeout: 1000,
    });

    await page
      .getByTestId("input_outputText Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 500, y: 100 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("filter data");
    await page.waitForSelector("text=Filter Data", {
      timeout: 1000,
    });

    await page
      .getByTestId("processingFilter Data")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 600, y: 200 },
      });

    await updateOldComponents(page);

    await page.getByTestId("fit_view").click();

    await page
      .getByTestId("textarea_str_template")
      .last()
      .fill("{similarity_score}");

    await page
      .getByTestId("popover-anchor-input-message")
      .last()
      .fill("datastax");
    await page
      .getByTestId("popover-anchor-input-message")
      .first()
      .fill("langflow");

    const firstApiKeyInput = page
      .getByTestId("popover-anchor-input-openai_api_key")
      .nth(0);
    const secondApiKeyInput = page
      .getByTestId("popover-anchor-input-openai_api_key")
      .nth(1);

    const isFirstInputVisible = await firstApiKeyInput.isVisible();
    const isSecondInputVisible = await secondApiKeyInput.isVisible();

    if (isFirstInputVisible) {
      await firstApiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
    }

    if (isSecondInputVisible) {
      await secondApiKeyInput.fill(process.env.OPENAI_API_KEY ?? "");
    }

    await page
      .getByTestId("inputlist_str_filter_criteria_0")
      .nth(0)
      .fill("similarity_score");

    await page.getByTestId("fit_view").click();
    await page.mouse.wheel(0, 500);

    await page.locator(".react-flow__pane").click();

    await page.getByTestId("fit_view").click();

    //connection 1
    const openAiEmbeddingOutput_0 = await page
      .getByTestId("handle-openaiembeddings-shownode-embedding model-right")
      .nth(0);
    await openAiEmbeddingOutput_0.hover();
    await page.mouse.down();

    const textEmbedderInput_0 = await page
      .getByTestId("handle-textembeddercomponent-shownode-embedding model-left")
      .nth(0);
    await textEmbedderInput_0.hover();
    await page.mouse.up();

    //connection 2
    const openAiEmbeddingOutput_1 = await page
      .getByTestId("handle-openaiembeddings-shownode-embedding model-right")
      .nth(0);
    await openAiEmbeddingOutput_1.hover();
    await page.mouse.down();
    const textEmbedderInput_1 = await page
      .getByTestId("handle-textembeddercomponent-shownode-embedding model-left")
      .nth(1);
    await textEmbedderInput_1.hover();
    await page.mouse.up();

    //connection 3
    const textEmbedderOutput_0 = await page
      .getByTestId("handle-textembeddercomponent-shownode-embedding data-right")
      .nth(0);
    await textEmbedderOutput_0.hover();
    await page.mouse.down();
    const embeddingSimilarityInput = await page
      .getByTestId(
        "handle-embeddingsimilaritycomponent-shownode-embedding vectors-left",
      )
      .nth(0);
    await embeddingSimilarityInput.hover();
    await page.mouse.up();

    //connection 4
    const textEmbedderOutput_1 = await page
      .getByTestId("handle-textembeddercomponent-shownode-embedding data-right")
      .nth(1);
    await textEmbedderOutput_1.hover();
    await page.mouse.down();
    await embeddingSimilarityInput.hover();
    await page.mouse.up();

    //connection 5
    const embeddingSimilarityOutput = await page
      .getByTestId(
        "handle-embeddingsimilaritycomponent-shownode-similarity data-right",
      )
      .nth(0);
    await embeddingSimilarityOutput.hover();
    await page.mouse.down();
    const filterDataInput = await page
      .getByTestId("handle-filterdata-shownode-data-left")
      .nth(0);
    await filterDataInput.hover();
    await page.mouse.up();

    //connection 6
    const filterDataOutput = await page
      .getByTestId("handle-filterdata-shownode-filtered data-right")
      .nth(0);
    await filterDataOutput.hover();
    await page.mouse.down();
    const parseDataInput = await page
      .getByTestId("handle-parsedata-shownode-data-left")
      .nth(0);
    await parseDataInput.hover();
    await page.mouse.up();

    //connection 7
    const parseDataOutput = await page
      .getByTestId("handle-parsedata-shownode-message-right")
      .nth(0);
    await parseDataOutput.hover();
    await page.mouse.down();
    const textOutputInput = await page
      .getByTestId("handle-textoutput-shownode-inputs-left")
      .nth(0);
    await textOutputInput.hover();
    await page.mouse.up();

    await page.getByTestId("button_run_text output").click();

    await page.waitForSelector("text=built successfully", { timeout: 30000 });

    await page
      .getByTestId(/rf__node-TextOutput-[a-zA-Z0-9]{5}/)
      .getByTestId("output-inspection-output text-textoutput")
      .first()
      .click();
    const valueSimilarity = await page.getByTestId("textarea").textContent();

    expect(valueSimilarity).toContain("cosine_similarity");
    const valueLength = valueSimilarity!.length;
    expect(valueLength).toBeGreaterThan(20);
  },
);
