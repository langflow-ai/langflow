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

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(3000);

  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 100000,
  });

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("api request");

  await page.waitForTimeout(2000);
  await page
    .getByTestId("dataAPI Request")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.waitForTimeout(500);

  await page.getByTestId("handle-apirequest-shownode-urls-left").click();

  await expect(page.getByTestId("disclosure-inputs")).toBeVisible();
  await expect(page.getByTestId("disclosure-outputs")).toBeVisible();
  await expect(page.getByTestId("disclosure-prompts")).toBeVisible();
  await expect(page.getByTestId("disclosure-models")).toBeVisible();
  await expect(page.getByTestId("disclosure-helpers")).toBeVisible();
  await expect(page.getByTestId("disclosure-agents")).toBeVisible();
  await expect(page.getByTestId("disclosure-chains")).toBeVisible();
  await expect(page.getByTestId("disclosure-prototypes")).toBeVisible();

  await expect(page.getByTestId("inputsChat Input")).toBeVisible();
  await expect(page.getByTestId("outputsChat Output")).toBeVisible();
  await expect(page.getByTestId("promptsPrompt")).toBeVisible();
  await expect(page.getByTestId("modelsAmazon Bedrock")).toBeVisible();
  await expect(page.getByTestId("helpersChat Memory")).toBeVisible();
  await expect(page.getByTestId("agentsTool Calling Agent")).toBeVisible();
  await expect(page.getByTestId("chainsConversationChain")).toBeVisible();
  await expect(page.getByTestId("prototypesConditional Router")).toBeVisible();

  await page.getByPlaceholder("Search").click();

  await expect(page.getByTestId("inputsChat Input")).not.toBeVisible();
  await expect(page.getByTestId("outputsChat Output")).not.toBeVisible();
  await expect(page.getByTestId("promptsPrompt")).not.toBeVisible();
  await expect(page.getByTestId("modelsAmazon Bedrock")).not.toBeVisible();
  await expect(page.getByTestId("helpersChat Memory")).not.toBeVisible();
  await expect(page.getByTestId("agentsTool Calling Agent")).not.toBeVisible();
  await expect(page.getByTestId("chainsConversationChain")).not.toBeVisible();
  await expect(
    page.getByTestId("prototypesConditional Router"),
  ).not.toBeVisible();

  await page.getByTestId("handle-apirequest-shownode-headers-left").click();

  await expect(page.getByTestId("disclosure-data")).toBeVisible();
  await expect(page.getByTestId("disclosure-helpers")).toBeVisible();
  await expect(page.getByTestId("disclosure-vector stores")).toBeVisible();
  await expect(page.getByTestId("disclosure-utilities")).toBeVisible();
  await expect(page.getByTestId("disclosure-prototypes")).toBeVisible();
  await expect(page.getByTestId("disclosure-retrievers")).toBeVisible();
  await expect(page.getByTestId("disclosure-text splitters")).toBeVisible();
  await expect(page.getByTestId("disclosure-tools")).toBeVisible();

  await expect(page.getByTestId("dataAPI Request")).toBeVisible();
  await expect(page.getByTestId("helpersChat Memory")).toBeVisible();
  await expect(page.getByTestId("vectorstoresAstra DB")).toBeVisible();
  await expect(page.getByTestId("langchain_utilitiesSearchApi")).toBeVisible();
  await expect(page.getByTestId("prototypesSub Flow")).toBeVisible();
  await expect(
    page.getByTestId("retrieversSelf Query Retriever"),
  ).toBeVisible();
  await expect(
    page.getByTestId("textsplittersCharacterTextSplitter"),
  ).toBeVisible();
  await expect(page.getByTestId("toolsSearchApi")).toBeVisible();

  await page.getByPlaceholder("Search").click();

  await expect(page.getByTestId("dataAPI Request")).not.toBeVisible();
  await expect(page.getByTestId("helpersChat Memory")).not.toBeVisible();
  await expect(page.getByTestId("vectorstoresAstra DB")).not.toBeVisible();
  await expect(
    page.getByTestId("langchain_utilitiesSearchApi"),
  ).not.toBeVisible();
  await expect(page.getByTestId("prototypesSub Flow")).not.toBeVisible();
  await expect(
    page.getByTestId("retrieversSelf Query Retriever"),
  ).not.toBeVisible();
  await expect(
    page.getByTestId("textsplittersCharacterTextSplitter"),
  ).not.toBeVisible();
  await expect(page.getByTestId("toolsSearchApi")).not.toBeVisible();
});
