import { expect, test } from "../../fixtures";
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

    await page.waitForSelector('[data-testid="data_sourceAPI Request"]', {
      timeout: 3000,
    });
    await page
      .getByTestId("data_sourceAPI Request")
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

    await expect(page.getByTestId("disclosure-input & output")).toBeVisible();
    await expect(page.getByTestId("disclosure-models & agents")).toBeVisible();
    await expect(page.getByTestId("disclosure-llm operations")).toBeVisible();
    await expect(page.getByTestId("disclosure-data sources")).toBeVisible();

    await page.getByTestId("sidebar-options-trigger").click();
    await page
      .getByTestId("sidebar-legacy-switch")
      .isVisible({ timeout: 5000 });
    await page.getByTestId("sidebar-legacy-switch").click();
    await page.getByTestId("sidebar-options-trigger").click();

    await expect(page.getByTestId("input_outputChat Input")).toBeVisible();
    await expect(page.getByTestId("input_outputChat Output")).toBeVisible();
    await expect(
      page.getByTestId("models_and_agentsPrompt Template"),
    ).toBeVisible();
    await expect(
      page.getByTestId("langchain_utilitiesCSV Agent"),
    ).toBeVisible();
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
      page.getByTestId("models_and_agentsPrompt Template"),
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

    await expect(page.getByTestId("disclosure-data sources")).toBeVisible();
    await expect(page.getByTestId("disclosure-llm operations")).toBeVisible();
    await expect(page.getByTestId("disclosure-processing")).toBeVisible();

    await expect(page.getByTestId("data_sourceAPI Request")).toBeVisible();
    await expect(page.getByTestId("datastaxAstra DB")).toBeVisible();
    await expect(page.getByTestId("flow_controlsSub Flow")).toBeVisible();

    await page.getByTestId("sidebar-options-trigger").click();
    await page.getByTestId("sidebar-beta-switch").isVisible({ timeout: 5000 });
    await page.getByTestId("sidebar-beta-switch").click();
    await expect(page.getByTestId("sidebar-beta-switch")).toBeChecked();
    await page.getByTestId("sidebar-options-trigger").click();

    await expect(page.getByTestId("flow_controlsSub Flow")).toBeVisible();

    await expect(page.getByTestId("processingData Operations")).toBeVisible();

    await page.getByTestId("icon-X").first().click();

    await expect(page.getByTestId("data_sourceAPI Request")).not.toBeVisible();
    await expect(page.getByTestId("datastaxAstra DB")).not.toBeVisible();
    await expect(page.getByTestId("flow_controlsSub Flow")).not.toBeVisible();

    await expect(page.getByTestId("processingSplit Text")).not.toBeVisible();
  },
);
