import { expect, test } from "@playwright/test";

test("RetrievalQA - Tooltip", async ({ page }) => {
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
    await page.waitForTimeout(5000);
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
    await expect(
      page.getByTestId("available-output-inputs").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-chains").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-textsplitters").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-retrievers").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-prototypes").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-embeddings").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-data").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-vectorstores").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-memories").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-models").first(),
    ).toBeVisible();

    await expect(
      page.getByTestId("available-output-outputs").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-agents").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-helpers").first(),
    ).toBeVisible();

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
    await page.waitForTimeout(2000);

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
    await page.waitForTimeout(2000);

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
      page.getByTestId("available-input-memories").first(),
    ).toBeVisible();
  });
});
