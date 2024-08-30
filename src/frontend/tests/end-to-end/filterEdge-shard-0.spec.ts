import { expect, test } from "@playwright/test";

test("user must see on handle hover a tooltip with possibility connections", async ({
  page,
}) => {
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
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

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

  const outputElements = await page
    .getByTestId("handle-retrievalqa-shownode-text-right")
    .all();
  let visibleElementHandle;

  for (const element of outputElements) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover().then(async () => {
    const testIds = [
      "available-output-inputs",
      "available-output-chains",
      "available-output-textsplitters",
      "available-output-retrievers",
      "available-output-prototypes",
      "available-output-embeddings",
      "available-output-data",
      "available-output-vectorstores",
      "available-output-memories",
      "available-output-models",
      "available-output-outputs",
      "available-output-agents",
      "available-output-helpers",
    ];

    await Promise.all(
      testIds.map((id) => expect(page.getByTestId(id).first()).toBeVisible()),
    );

    await page.getByTestId("icon-X").click();
    await page.waitForTimeout(500);
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  const rqaChainInputElements1 = await page
    .getByTestId("handle-retrievalqa-shownode-language model-left")
    .all();

  for (const element of rqaChainInputElements1) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover().then(async () => {
    await expect(
      page.getByTestId("available-input-models").first(),
    ).toBeVisible();
    await page.waitForTimeout(1000);

    await page.getByTestId("icon-Search").click();

    await page.waitForTimeout(500);
  });
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  const rqaChainInputElements0 = await page
    .getByTestId("handle-retrievalqa-shownode-retriever-left")
    .all();

  for (const element of rqaChainInputElements0) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover().then(async () => {
    await page.waitForTimeout(2500);

    await expect(
      page.getByTestId("available-input-retrievers").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-input-vectorstores").first(),
    ).toBeVisible();

    await page.waitForTimeout(500);
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  const rqaChainInputElements2 = await page
    .getByTestId("handle-retrievalqa-shownode-memory-left")
    .all();

  for (const element of rqaChainInputElements2) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover().then(async () => {
    await expect(
      page.getByTestId("available-input-helpers").first(),
    ).toBeVisible();
  });
});
