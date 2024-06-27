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
    timeout: 100000,
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
  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[7]/button/div[1]',
    )
    .hover()
    .then(async () => {
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
  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[4]/div/button/div[1]',
    )
    .hover()
    .then(async () => {
      await expect(
        page.getByTestId("available-input-models").first(),
      ).toBeVisible();
      await page.waitForTimeout(2000);

      await page.getByTestId("icon-Search").click();

      await page.waitForTimeout(500);
    });

  await page.waitForSelector('[title="fit view"]', {
    timeout: 100000,
  });

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div/div/div[2]/div/div/div[2]/div[3]/div/button/div[1]',
    )
    .hover()
    .then(async () => {
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

  await page
    .locator(
      '//*[@id="react-flow-id"]/div/div[1]/div[1]/div/div[2]/div/div/div[2]/div[5]/div/button/div[1]',
    )
    .hover()
    .then(async () => {
      await expect(
        page.getByTestId("empty-tooltip-filter").first(),
      ).toBeVisible();
    });
});
