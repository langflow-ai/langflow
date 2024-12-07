import { expect, test } from "@playwright/test";

test(
  "user must see on handle click the possibility connections",
  { tag: ["@release", "@components", "@api"] },

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
      const modalTitleElement = await page?.getByTestId("modal-title");
      if (modalTitleElement) {
        modalCount = await modalTitleElement.count();
      }
    } catch (error) {
      modalCount = 0;
    }

    while (modalCount === 0) {
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }
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
    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.waitForSelector(
      '[data-testid="handle-apirequest-shownode-urls-left"]',
      {
        timeout: 3000,
      },
    );
    await page.getByTestId("handle-apirequest-shownode-urls-left").click();

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

    await expect(page.getByTestId("disclosure-inputs")).toBeVisible();
    await expect(page.getByTestId("disclosure-outputs")).toBeVisible();
    await expect(page.getByTestId("disclosure-prompts")).toBeVisible();
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

    await expect(page.getByTestId("inputsChat Input")).toBeVisible();
    await expect(page.getByTestId("outputsChat Output")).toBeVisible();
    await expect(page.getByTestId("promptsPrompt")).toBeVisible();
    await expect(page.getByTestId("modelsAmazon Bedrock")).toBeVisible();
    await expect(page.getByTestId("helpersMessage History")).toBeVisible();
    await expect(page.getByTestId("langchain_utilitiesCSVAgent")).toBeVisible();
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

    await expect(page.getByTestId("inputsChat Input")).not.toBeVisible();
    await expect(page.getByTestId("outputsChat Output")).not.toBeVisible();
    await expect(page.getByTestId("promptsPrompt")).not.toBeVisible();
    await expect(page.getByTestId("modelsAmazon Bedrock")).not.toBeVisible();
    await expect(page.getByTestId("helpersMessage History")).not.toBeVisible();
    await expect(
      page.getByTestId("agentsTool Calling Agent"),
    ).not.toBeVisible();
    await expect(
      page.getByTestId("langchain_utilitiesConversationChain"),
    ).not.toBeVisible();
    await expect(page.getByTestId("logicCondition")).not.toBeVisible();

    await page.getByTestId("handle-apirequest-shownode-headers-left").click();

    await expect(page.getByTestId("disclosure-data")).toBeVisible();
    await expect(page.getByTestId("disclosure-helpers")).toBeVisible();
    await expect(page.getByTestId("disclosure-vector stores")).toBeVisible();
    await expect(page.getByTestId("disclosure-prototypes")).toBeVisible();
    await expect(page.getByTestId("disclosure-embeddings")).toBeVisible();
    await expect(page.getByTestId("disclosure-tools")).toBeVisible();

    await expect(page.getByTestId("dataAPI Request")).toBeVisible();
    await expect(page.getByTestId("helpersMessage History")).toBeVisible();
    await expect(page.getByTestId("vectorstoresAstra DB")).toBeVisible();
    await expect(page.getByTestId("toolsSearch API")).toBeVisible();
    await expect(page.getByTestId("logicSub Flow")).not.toBeVisible();

    await page.getByTestId("sidebar-options-trigger").click();
    await page.getByTestId("sidebar-beta-switch").isVisible({ timeout: 5000 });
    await page.getByTestId("sidebar-beta-switch").click();
    await expect(page.getByTestId("sidebar-beta-switch")).toBeChecked();
    await page.getByTestId("sidebar-options-trigger").click();

    await expect(page.getByTestId("logicSub Flow")).toBeVisible();

    await expect(page.getByTestId("processingSplit Text")).toBeVisible();
    await expect(page.getByTestId("toolsSearch API")).toBeVisible();

    await page.getByTestId("icon-X").first().click();

    await expect(page.getByTestId("dataAPI Request")).not.toBeVisible();
    await expect(page.getByTestId("helpersMessage History")).not.toBeVisible();
    await expect(page.getByTestId("vectorstoresAstra DB")).not.toBeVisible();
    await expect(page.getByTestId("toolsSearch API")).not.toBeVisible();
    await expect(page.getByTestId("logicSub Flow")).not.toBeVisible();

    await expect(page.getByTestId("processingSplit Text")).not.toBeVisible();
    await expect(page.getByTestId("toolsSearch API")).not.toBeVisible();
  },
);
