import { expect, test } from "../../fixtures";
import { addLegacyComponents } from "../../utils/add-legacy-components";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must see on handle hover a tooltip with possibility connections",
  { tag: ["@release", "@components", "@api"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("retrievalqa");

    await addLegacyComponents(page);

    await page.waitForTimeout(1000);
    await page
      .getByTestId("langchain_utilitiesRetrieval QA")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page, { numberOfZoomOut: 3 });

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
        page.getByText("Drag to connect compatible inputs").first(),
      ).toBeVisible();

      await expect(
        page
          .getByText("Click to filter compatible inputs and components")
          .first(),
      ).toBeVisible();

      await expect(page.getByText("Output type:").first()).toBeVisible();

      await expect(
        page.getByTestId("output-tooltip-message").first(),
      ).toBeVisible();
    });

    await adjustScreenView(page);

    const rqaChainInputElements1 = await page
      .getByTestId("handle-retrievalqa-shownode-language model-left")
      .all();

    await page.waitForTimeout(1000);

    for (const element of rqaChainInputElements1) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    await page.waitForTimeout(500);

    await visibleElementHandle.hover().then(async () => {
      await page.waitForTimeout(1000);

      await expect(
        page.getByText("Drag to connect compatible outputs").first(),
      ).toBeVisible();

      await expect(
        page
          .getByText("Click to filter compatible outputs and components")
          .first(),
      ).toBeVisible();

      await expect(page.getByText("Input type:").first()).toBeVisible();

      await expect(
        page.getByTestId("input-tooltip-languagemodel").first(),
      ).toBeVisible();
    });
    await adjustScreenView(page);

    const rqaChainInputElements0 = await page
      .getByTestId("handle-retrievalqa-shownode-retriever-left")
      .all();

    for (const element of rqaChainInputElements0) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    await page.waitForTimeout(500);

    await visibleElementHandle.hover().then(async () => {
      await page.waitForTimeout(1000);

      await expect(
        page.getByText("Drag to connect compatible outputs").first(),
      ).toBeVisible();

      await expect(
        page
          .getByText("Click to filter compatible outputs and components")
          .first(),
      ).toBeVisible();

      await expect(page.getByText("Input type:").first()).toBeVisible();

      await expect(
        page.getByTestId("input-tooltip-retriever").first(),
      ).toBeVisible();
    });

    await adjustScreenView(page);

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
        page.getByText("Drag to connect compatible outputs").first(),
      ).toBeVisible();

      await expect(
        page
          .getByText("Click to filter compatible outputs and components")
          .first(),
      ).toBeVisible();

      await expect(page.getByText("Input type:").first()).toBeVisible();

      await expect(
        page.getByTestId("input-tooltip-basechatmemory").first(),
      ).toBeVisible();
    });
  },
);
