import { expect, test } from "@playwright/test";

test("user should be able to connect RetrieverTool to another components", async ({
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
    const modalTitleElement = await page.getByTestId("modal-title");
    modalCount = await modalTitleElement.count();
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(3000);
    modalCount = await page.getByTestId("modal-title").count();
  }

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });
  await page.getByTestId("blank-flow").click();
  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("retriever");

  await page.waitForTimeout(1000);

  let modelElement = await page.getByTestId("toolsRetrieverTool");
  let targetElement = await page.locator('//*[@id="react-flow-id"]');
  await modelElement.dragTo(targetElement);

  await page.mouse.up();
  await page.mouse.down();

  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();

  await page.waitForTimeout(1000);

  await page.getByTitle("zoom out").click();
  await page
    .locator('//*[@id="react-flow-id"]')
    .hover()
    .then(async () => {
      await page.mouse.down();
      await page.mouse.move(-500, 500);
    });

  await page.mouse.up();

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("chroma");

  await page.waitForTimeout(1000);

  modelElement = await page.getByTestId("vectorstoresChroma DB");
  targetElement = await page.locator('//*[@id="react-flow-id"]');
  await modelElement.dragTo(targetElement);

  await page.mouse.up();
  await page.mouse.down();

  await page.waitForTimeout(1000);

  await page.getByTitle("fit view").click();
  await page.getByTitle("fit view").click();

  //connection
  const chromaDbOutput = await page
    .getByTestId("handle-chroma-shownode-retriever-right")
    .nth(0);
  await chromaDbOutput.hover();
  await page.mouse.down();
  const retrieverToolInput = await page
    .getByTestId("handle-retrievertool-shownode-retriever-left")
    .nth(0);
  await retrieverToolInput.hover();
  await page.mouse.up();

  await page.waitForTimeout(1000);

  expect(await page.locator(".react-flow__edge-interaction").count()).toBe(1);
});
