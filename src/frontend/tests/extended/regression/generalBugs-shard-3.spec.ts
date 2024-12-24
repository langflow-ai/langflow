import { expect, test } from "@playwright/test";
import * as dotenv from "dotenv";
import path from "path";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { initialGPTsetup } from "../../utils/initialGPTsetup";

test(
  "should copy code from playground modal",
  {
    tag: ["@release"],
  },
  async ({ page }) => {
    test.skip(
      !process?.env?.OPENAI_API_KEY,
      "OPENAI_API_KEY required to run this test",
    );

    if (!process.env.CI) {
      dotenv.config({ path: path.resolve(__dirname, "../../.env") });
    }
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });
    await page.getByTestId("sidebar-search-input").click();

    await adjustScreenView(page, { numberOfZoomOut: 4 });

    await page.getByTestId("sidebar-search-input").fill("chat output");

    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("outputsChat Output")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 0, y: 0 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat input");
    await page.waitForSelector('[data-testid="inputsChat Input"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("inputsChat Input")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 50, y: 200 },
      });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("openai");

    await page
      .getByTestId("modelsOpenAI")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 300, y: 200 },
      });

    await page.getByTestId("fit_view").click();

    await page.getByTestId("title-Chat Input").click();
    await page.keyboard.press("ControlOrMeta+.");

    await page.getByTestId("title-Chat Output").click();
    await page.keyboard.press("ControlOrMeta+.");

    await initialGPTsetup(page);
    await initialGPTsetup(page);

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 5000,
      state: "visible",
    });

    const elementsChatInput = await page
      .locator('[data-testid="handle-chatinput-shownode-message-right"]')
      .all();

    let visibleElementHandle;

    for (const element of elementsChatInput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    await visibleElementHandle.hover();
    await page.mouse.down();

    const elementsOpenAiInput = await page
      .locator('[data-testid="handle-openaimodel-shownode-input-left"]')
      .all();

    for (const element of elementsOpenAiInput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    await visibleElementHandle.hover();
    await page.mouse.up();

    const elementsOpenAiOutput = await page
      .locator('[data-testid="handle-openaimodel-shownode-text-right"]')
      .all();

    for (const element of elementsOpenAiOutput) {
      if (await element.isVisible()) {
        visibleElementHandle = element;
        break;
      }
    }

    await page
      .getByTestId("handle-chatoutput-shownode-text-left")
      .first()
      .click();
    await page
      .getByTestId("handle-openaimodel-shownode-text-right")
      .first()
      .click();

    await page.getByTestId("fit_view").click();
    await page.getByText("Playground", { exact: true }).last().click();
    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });
    await page.getByTestId("input-chat-playground").click();
    await page
      .getByTestId("input-chat-playground")
      .fill(
        "Could you provide a Python example for a 'Hello, World!' program?",
      );

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();

    await page.getByRole("tab", { name: "python" }).isVisible({
      timeout: 100000,
    });

    await page.waitForSelector('[data-testid="copy-code-button"]', {
      state: "visible",
      timeout: 30000,
    });

    await page.getByTestId("copy-code-button").last().click();

    const handle = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent = await handle.jsonValue();
    expect(clipboardContent.length).toBeGreaterThan(0);
    expect(clipboardContent).toContain("Hello");
  },
);

test(
  "playground button should be enabled or disabled",
  { tag: ["@release", "@api", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });

    await page.getByTestId("blank-flow").click();

    expect(await page.getByTestId("playground-btn-flow").isDisabled());

    expect(await page.getByText("Langflow Chat").isHidden());

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("chat output");

    await page.waitForSelector('[data-testid="outputsChat Output"]', {
      timeout: 30000,
    });
    await page
      .locator('//*[@id="outputsChat Output"]')
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("playground-btn-flow-io").click({ force: true });

    expect(await page.getByText("Langflow Chat").isVisible());
  },
);
