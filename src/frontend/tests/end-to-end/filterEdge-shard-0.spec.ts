import { expect, test } from "@playwright/test";

test("LLMChain - Tooltip", async ({ page }) => {
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
  await page.getByPlaceholder("Search").fill("llmchain");

  await page.waitForTimeout(1000);
  await page
    .getByTestId("chainsLLMChain")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  const llmChainOutputElements = await page
    .getByTestId("handle-llmchain-shownode-text-right")
    .all();
  let visibleElementHandle;

  for (const element of llmChainOutputElements) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover().then(async () => {
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
      page.getByTestId("available-output-tools").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-memories").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-toolkits").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-chains").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-agents").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-helpers").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-output-langchain_utilities").first(),
    ).toBeVisible();

    await page.getByTestId("icon-X").click();
    await page.waitForTimeout(500);
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  const llmChainInputElements1 = await page
    .getByTestId("handle-llmchain-shownode-llm-left")
    .all();

  for (const element of llmChainInputElements1) {
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

  const llmChainInputElements0 = await page
    .getByTestId("handle-llmchain-shownode-template-left")
    .all();

  for (const element of llmChainInputElements0) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover().then(async () => {
    await page.waitForTimeout(2000);

    await expect(
      page.getByTestId("available-input-chains").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-input-prototypes").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-input-agents").first(),
    ).toBeVisible();
    await expect(
      page.getByTestId("available-input-helpers").first(),
    ).toBeVisible();

    await page.waitForTimeout(500);
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  const llmChainInputElements2 = await page
    .getByTestId("handle-llmchain-shownode-memory-left")
    .all();

  for (const element of llmChainInputElements2) {
    if (await element.isVisible()) {
      visibleElementHandle = element;
      break;
    }
  }

  await visibleElementHandle.hover().then(async () => {
    await expect(
      page.getByTestId("empty-tooltip-filter").first(),
    ).toBeVisible();
  });
});
