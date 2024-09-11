import { expect, test } from "@playwright/test";

test("user must see on handle click the possibility connections - LLMChain", async ({
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

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(3000);

  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 100000,
  });

  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("api request");

  await page.waitForTimeout(1000);
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

  let disclosureTestIds = [
    "disclosure-inputs",
    "disclosure-outputs",
    "disclosure-prompts",
    "disclosure-models",
    "disclosure-helpers",
    "disclosure-agents",
    "disclosure-chains",
    "disclosure-prototypes",
  ];

  let specificTestIds = [
    "inputsChat Input",
    "outputsChat Output",
    "promptsPrompt",
    "modelsAmazon Bedrock",
    "helpersChat Memory",
    "agentsCSVAgent",
    "chainsConversationChain",
    "prototypesConditional Router",
  ];

  await Promise.all(
    disclosureTestIds.map((id) => expect(page.getByTestId(id)).toBeVisible()),
  );

  await Promise.all(
    specificTestIds.map((id) => expect(page.getByTestId(id)).toBeVisible()),
  );

  await page.getByPlaceholder("Search").click();

  let notVisibleTestIds = [
    "inputsChat Input",
    "outputsChat Output",
    "promptsPrompt",
    "modelsAmazon Bedrock",
    "helpersChat Memory",
    "agentsTool Calling Agent",
    "chainsConversationChain",
    "prototypesConditional Router",
  ];

  await Promise.all(
    notVisibleTestIds.map((id) =>
      expect(page.getByTestId(id)).not.toBeVisible(),
    ),
  );

  await page.getByTestId("handle-apirequest-shownode-headers-left").click();

  disclosureTestIds = [
    "disclosure-data",
    "disclosure-helpers",
    "disclosure-vector stores",
    "disclosure-utilities",
    "disclosure-prototypes",
    "disclosure-retrievers",
    "disclosure-tools",
  ];

  specificTestIds = [
    "dataAPI Request",
    "helpersChat Memory",
    "vectorstoresAstra DB",
    "toolsSearch API",
    "prototypesSub Flow",
    "retrieversSelf Query Retriever",
  ];

  await Promise.all(
    disclosureTestIds.map((id) => expect(page.getByTestId(id)).toBeVisible()),
  );

  await Promise.all(
    specificTestIds.map((id) => expect(page.getByTestId(id)).toBeVisible()),
  );

  await page.getByPlaceholder("Search").click();

  notVisibleTestIds = [
    "dataAPI Request",
    "helpersChat Memory",
    "vectorstoresAstra DB",
    "toolsSearch API",
    "prototypesSub Flow",
    "retrieversSelf Query Retriever",
    "textsplittersCharacterTextSplitter",
  ];

  await Promise.all(
    notVisibleTestIds.map((id) =>
      expect(page.getByTestId(id)).not.toBeVisible(),
    ),
  );
});
