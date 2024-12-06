import { expect, test } from "@playwright/test";

test(
  "user should be able to use ComposIO without getting api_key error",
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
    await page.getByTestId("sidebar-search-input").fill("composio");

    await page.waitForSelector('[data-testid="composioComposio Tools"]', {
      timeout: 3000,
    });

    const modelElement = await page.getByTestId("composioComposio Tools");
    const targetElement = await page.locator('//*[@id="react-flow-id"]');
    await modelElement.dragTo(targetElement);

    await page.mouse.up();
    await page.mouse.down();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await expect(page.getByText("api_key")).toBeVisible({ timeout: 3000,visible: false });
  },
);

test(
  "user should be able to use connect tools",
  { tag: ["@release", "@api", "@components"] },
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
    await page.getByTestId("sidebar-search-input").fill("search api");

    await page.waitForSelector('[data-testid="toolsSearch API"]', {
      timeout: 3000,
    });

    let modelElement = await page.getByTestId("toolsSearch API");
    let targetElement = await page.locator('//*[@id="react-flow-id"]');
    await modelElement.dragTo(targetElement);

    await page.mouse.up();
    await page.mouse.down();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("tool calling agent");

    await page.waitForSelector('[data-testid="langchain_utilitiesTool Calling Agent"]', {
      timeout: 3000,
    });

    modelElement = page.getByTestId(
      "langchain_utilitiesTool Calling Agent",
    );
    targetElement = await page.locator('//*[@id="react-flow-id"]');
    await modelElement.dragTo(targetElement);

    await page.mouse.up();
    await page.mouse.down();

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    //connection
    const searchApiOutput = await page
      .getByTestId("handle-searchapi-shownode-tool-right")
      .nth(0);
    await searchApiOutput.hover();
    await page.mouse.down();
    const toolCallingAgentInput = await page
      .getByTestId("handle-toolcallingagent-shownode-tools-left")
      .nth(0);
    await toolCallingAgentInput.hover();
    await page.mouse.up();


    expect(await page.locator(".react-flow__edge-interaction").count()).toBe(1);
  },
);
