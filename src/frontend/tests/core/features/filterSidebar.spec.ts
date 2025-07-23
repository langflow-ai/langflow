import { expect, test } from "@playwright/test";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must see on handle click the possibility connections",
  { tag: ["@release", "@components", "@api"] },

  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 3000,
    });

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 3000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("api request");

    await page.waitForSelector('[data-testid="dataAPI Request"]', {
      timeout: 3000,
    });
    await page
      .getByTestId("dataAPI Request")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    await page.waitForSelector(
      '[data-testid="handle-apirequest-shownode-url-left"]',
      {
        timeout: 3000,
      },
    );
    await page.getByTestId("handle-apirequest-shownode-url-left").click();

    await page.waitForTimeout(500);

    expect(await page.getByTestId("icon-ListFilter").first()).toBeVisible();

    await page
      .getByTestId("icon-X")
      .first()
      .hover()
      .then(async () => {
        await page
          .getByText("Remove filter", {
            exact: false,
          })
          .first()
          .isVisible();
      });

    await expect(page.getByTestId("disclosure-input / output")).toBeVisible();
    await expect(page.getByTestId("disclosure-models")).toBeVisible();
    await expect(page.getByTestId("disclosure-helpers")).toBeVisible();
    await expect(page.getByTestId("disclosure-agents")).toBeVisible();

    await page.getByTestId("sidebar-options-trigger").click();
    await page
      .getByTestId("sidebar-legacy-switch")
      .isVisible({ timeout: 5000 });
    await page.getByTestId("sidebar-legacy-switch").click();
    await page.getByTestId("sidebar-options-trigger").click();

    await expect(page.getByTestId("disclosure-prototypes")).toBeVisible();

    await expect(page.getByTestId("input_outputChat Input")).toBeVisible();
    await expect(page.getByTestId("input_outputChat Output")).toBeVisible();
    await expect(page.getByTestId("processingPrompt Template")).toBeVisible();
    await expect(page.getByTestId("langchain_utilitiesCSV Agent")).toBeVisible();
    await expect(
      page.getByTestId("langchain_utilitiesConversationChain"),
    ).toBeVisible();

    await expect(
      page.getByTestId("langchain_utilitiesPrompt Hub"),
    ).toBeVisible();

    await page.getByTestId("sidebar-options-trigger").click();
    await page.getByTestId("sidebar-beta-switch").isVisible({ timeout: 5000 });
    await page.getByTestId("sidebar-beta-switch").click();
    await expect(page.getByTestId("sidebar-beta-switch")).not.toBeChecked();
    await page.getByTestId("sidebar-options-trigger").click();

    await expect(
      page.getByTestId("langchain_utilitiesPrompt Hub"),
    ).not.toBeVisible();

    await page.getByTestId("sidebar-filter-reset").click();

    await expect(page.getByTestId("input_outputChat Input")).not.toBeVisible();
    await expect(page.getByTestId("input_outputChat Output")).not.toBeVisible();
    await expect(
      page.getByTestId("processingPrompt Template"),
    ).not.toBeVisible();
    await expect(
      page.getByTestId("agentsTool Calling Agent"),
    ).not.toBeVisible();
    await expect(
      page.getByTestId("langchain_utilitiesConversationChain"),
    ).not.toBeVisible();
    await expect(page.getByTestId("logicCondition")).not.toBeVisible();

    await page.getByTestId("edit-button-modal").click();

    await page.getByTestId("showheaders").click();
    await page.getByText("Close").last().click();
    await page.getByTestId("handle-apirequest-shownode-headers-left").click();

    await expect(page.getByTestId("disclosure-data")).toBeVisible();
    await expect(page.getByTestId("disclosure-helpers")).toBeVisible();
    await expect(page.getByTestId("disclosure-vector stores")).toBeVisible();
    await expect(page.getByTestId("disclosure-prototypes")).toBeVisible();
    await expect(page.getByTestId("disclosure-tools")).toBeVisible();

    await expect(page.getByTestId("dataAPI Request")).toBeVisible();
    await expect(page.getByTestId("vectorstoresAstra DB")).toBeVisible();
    await expect(page.getByTestId("logicSub Flow [Deprecated]")).toBeVisible();

    await page.getByTestId("sidebar-options-trigger").click();
    await page.getByTestId("sidebar-beta-switch").isVisible({ timeout: 5000 });
    await page.getByTestId("sidebar-beta-switch").click();
    await expect(page.getByTestId("sidebar-beta-switch")).toBeChecked();
    await page.getByTestId("sidebar-options-trigger").click();

    await expect(page.getByTestId("logicSub Flow [Deprecated]")).toBeVisible();

    await expect(page.getByTestId("processingData Operations")).toBeVisible();

    await page.getByTestId("icon-X").first().click();

    await expect(page.getByTestId("dataAPI Request")).not.toBeVisible();
    await expect(page.getByTestId("vectorstoresAstra DB")).not.toBeVisible();
    await expect(
      page.getByTestId("logicSub Flow [Deprecated]"),
    ).not.toBeVisible();

    await expect(page.getByTestId("processingSplit Text")).not.toBeVisible();
  },
);
