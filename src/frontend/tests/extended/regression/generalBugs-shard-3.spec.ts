import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import {
  configureLoopbackOpenAI,
  LOOPBACK_OPENAI_API_KEY,
} from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { skipIfComponentUnavailable } from "../../utils/skip-if-component-unavailable";

test(
  "should copy code from playground modal",
  {
    tag: ["@release"],
  },
  async ({ page }) => {
    await openBlankFlow(page);
    await addComponentFromSidebar(page, {
      search: TEXTS.searchChatOutput,
      testId: "input_outputChat Output",
      hoverAdd: true,
      addButtonSlug: "chat-output",
    });
    await expect(
      page.getByRole("group", { name: "Chat Output node" }),
    ).toBeAttached();
    await addComponentFromSidebar(page, {
      search: TEXTS.searchChatInput,
      testId: "input_outputChat Input",
      hoverAdd: true,
      addButtonSlug: "chat-input",
    });
    await expect(
      page.getByRole("group", { name: "Chat Input node" }),
    ).toBeAttached();

    await page.getByTestId("sidebar-search-input").click();
    await page
      .getByTestId("sidebar-search-input")
      .fill(TEXTS.providerOpenAiSearch);

    const openAIComponent = page.getByTestId("openaiOpenAI");
    await skipIfComponentUnavailable(openAIComponent, "OpenAI");

    await openAIComponent.dragTo(page.locator('//*[@id="react-flow-id"]'), {
      targetPosition: { x: 100, y: 200 },
    });

    await adjustScreenView(page);

    await page.getByText("OpenAI", { exact: true }).last().click();

    await expect(
      page.getByTestId("handle-chatinput-noshownode-chat message-source"),
    ).toBeVisible();

    if (await page.getByTestId("remove-icon-badge").isVisible()) {
      await page.getByTestId("remove-icon-badge").click();
    }

    if (await page.getByTestId("remove-icon-badge").isVisible()) {
      await page.getByTestId("remove-icon-badge").click();
    }

    await page
      .getByTestId("popover-anchor-input-api_key")
      .fill(LOOPBACK_OPENAI_API_KEY);

    await page
      .getByTestId("handle-chatinput-noshownode-chat message-source")
      .click();
    await page
      .getByTestId("handle-openaimodelcomponent-shownode-input-left")
      .click();

    await page
      .getByTestId("handle-openaimodelcomponent-shownode-model response-right")
      .click();
    await page
      .getByRole("group", { name: "Chat Output node" })
      .locator('[data-testid^="handle-chatoutput-"][data-testid*="-inputs-"]')
      .click();
    await configureLoopbackOpenAI(page);
    await adjustScreenView(page);

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();
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

    await page.getByTestId("api_tab_python").isVisible({
      timeout: 100000,
    });

    await page.waitForSelector('[data-testid="copy-code-button"]', {
      state: "visible",
      timeout: 30000,
    });

    await page.getByTestId("copy-code-button").first().click();

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
    await openBlankFlow(page);

    await expect(page.getByTestId("playground-btn-flow")).toBeDisabled();
    await expect(page.getByText("Langflow Chat")).toBeHidden();

    await addComponentFromSidebar(page, {
      search: TEXTS.searchChatOutput,
      testId: "input_outputChat Output",
      hoverAdd: true,
      addButtonSlug: "chat-output",
    });
    await expect(
      page.getByRole("group", { name: "Chat Output node" }),
    ).toBeAttached();

    await adjustScreenView(page);

    await expect(page.getByTestId("playground-btn-flow-io")).toBeEnabled();
    await page.getByTestId("playground-btn-flow-io").click({ force: true });

    await expect(page.getByText("Langflow Chat")).toBeVisible();
  },
);
