import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user should be able to connect RetrieverTool into another components",
  { tag: ["@release"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

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
        await page.mouse.move(-300, 100);
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

    await page
      .getByTestId(
        "vectorstoresVectara Self Query Retriever for Vectara Vector Store",
      )
      .hover()
      .then(async () => {
        await page
          .getByTestId(
            "add-component-button-vectara-self-query-retriever-for-vectara-vector-store",
          )
          .click();
      });

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 5000,
      state: "visible",
    });

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
