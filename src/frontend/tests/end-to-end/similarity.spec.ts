import { expect, test } from "@playwright/test";

test("user must be able to check similarity between embedding texts", async ({
  page,
}) => {
  test.skip(
    !process?.env?.OPENAI_API_KEY,
    "OPENAI_API_KEY required to run this test",
  );

  await page.goto("/");
  // await page.waitForTimeout(2000);

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

  await page.getByRole("heading", { name: "Blank Flow" }).click();

  //first component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("openai");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("embeddingsOpenAI Embeddings")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //second component

  await page
    .getByTestId("embeddingsOpenAI Embeddings")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //third component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("text embedder");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("embeddingsText Embedder")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //fourth component

  await page
    .getByTestId("embeddingsText Embedder")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //fifth component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("embedding similarity");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("embeddingsEmbedding Similarity")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //sisxth component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("parse data");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("helpersParse Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  //seventh component

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("text output");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("outputsText Output")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("filter data");
  // await page.waitForTimeout(1000);

  await page
    .getByTestId("helpersFilter Data")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-800, 300);
    });

  await page.mouse.up();

  let outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();

  while (outdatedComponents > 0) {
    await page.getByTestId("icon-AlertTriangle").first().click();
    // await page.waitForTimeout(1000);
    outdatedComponents = await page.getByTestId("icon-AlertTriangle").count();
  }

  await page.getByTitle("fit view").click();

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

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .nth(0)
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page
    .getByTestId("popover-anchor-input-openai_api_key")
    .nth(1)
    .fill(process.env.OPENAI_API_KEY ?? "");

  await page
    .getByTestId("inputlist_str_filter_criteria_0")
    .nth(0)
    .fill("similarity_score");

  //connection 1
  const openAiEmbeddingOutput_0 = await page
    .getByTestId("handle-openaiembeddings-shownode-embeddings-right")
    .nth(2);
  await openAiEmbeddingOutput_0.hover();
  await page.mouse.down();
  const textEmbedderInput_0 = await page
    .getByTestId("handle-textembeddercomponent-shownode-embedding model-left")
    .nth(0);
  await textEmbedderInput_0.hover();
  await page.mouse.up();

  //connection 2
  const openAiEmbeddingOutput_1 = await page
    .getByTestId("handle-openaiembeddings-shownode-embeddings-right")
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
    .nth(2);
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
    .getByTestId("handle-parsedata-shownode-text-right")
    .nth(0);
  await parseDataOutput.hover();
  await page.mouse.down();
  const textOutputInput = await page
    .getByTestId("handle-textoutput-shownode-text-left")
    .nth(0);
  await textOutputInput.hover();
  await page.mouse.up();

  await page.getByTestId("button_run_text output").click();

  await page.waitForSelector("text=built successfully", { timeout: 30000 });

  await page.waitForTimeout(1000);
  await page.getByText("Playground", { exact: true }).click();
  await page.waitForTimeout(1000);

  await page
    .getByPlaceholder("Empty")
    .waitFor({ state: "visible", timeout: 30000 });

  const valueSimilarity = await page.getByPlaceholder("Empty").textContent();
  expect(valueSimilarity).toContain("cosine_similarity");
  const valueLength = valueSimilarity!.length;
  expect(valueLength).toBeGreaterThan(20);
});
