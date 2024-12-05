import { expect, test } from "@playwright/test";

test(
  "user should be able to connect RetrieverTool into another components",
  { tag: ["@release"] },
  async ({ page }) => {
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
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title").count();
    }

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("retriever");

    await page.waitForSelector('[data-testid="sidebar-options-trigger"]', {
      timeout: 30000,
    });

    await page.getByTestId("sidebar-options-trigger").click();
    await page
      .getByTestId("sidebar-legacy-switch")
      .isVisible({ timeout: 5000 });
    await page.getByTestId("sidebar-legacy-switch").click();
    await expect(page.getByTestId("sidebar-legacy-switch")).toBeChecked();
    await page.getByTestId("sidebar-options-trigger").click();

    let modelElement = await page.getByTestId(
      "langchain_utilitiesRetrieverTool",
    );
    let targetElement = await page.locator('//*[@id="react-flow-id"]');
    await modelElement.dragTo(targetElement);

    await page.mouse.up();
    await page.mouse.down();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("zoom_out").click();
    await page
      .locator('//*[@id="react-flow-id"]')
      .hover()
      .then(async () => {
        await page.mouse.down();
        await page.mouse.move(-300, 300);
      });

    await page.mouse.up();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("Vectara");

    await page.waitForSelector(
      '[data-testid="vectorstoresVectara Self Query Retriever for Vectara Vector Store"]',
      {
        timeout: 30000,
      },
    );

    modelElement = page.getByTestId(
      "vectorstoresVectara Self Query Retriever for Vectara Vector Store",
    );
    targetElement = page.locator('//*[@id="react-flow-id"]');
    await modelElement.dragTo(targetElement);

    await page.mouse.up();
    await page.mouse.down();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("fit_view").click();

    //connection
    const vectaraOutput = page
      .getByTestId("handle-vectaraselfqueryretriver-shownode-retriever-right")
      .nth(0);
    await vectaraOutput.hover();
    await page.mouse.down();
    const retrieverToolInput = await page
      .getByTestId("handle-retrievertool-shownode-retriever-left")
      .nth(0);
    await retrieverToolInput.hover();
    await page.mouse.up();

    expect(await page.locator(".react-flow__edge-interaction").count()).toBe(1);
  },
);
