import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import { addComponentFromSidebar } from "../../utils/flow/add-component-from-sidebar";
import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";

test(
  "should copy code from playground modal",
  {
    tag: ["@release"],
  },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await openStarterProject(page, TEXTS.templateBasicPrompting);
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
      page.getByRole("application", { name: "Chat Output node" }),
    ).toBeAttached();

    await adjustScreenView(page);

    await expect(page.getByTestId("playground-btn-flow-io")).toBeEnabled();
    await page.getByTestId("playground-btn-flow-io").click({ force: true });

    await expect(
      page.getByRole("dialog", { name: "Playground" }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Add a Chat Input component to your flow to send messages.",
      ),
    ).toBeVisible();
  },
);
