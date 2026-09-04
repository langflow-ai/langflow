import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TEXTS } from "../../utils/constants/texts";
import {
  closeParametersPanel,
  openParametersPanel,
  toggleParameterOnNode,
} from "../../utils/open-advanced-options";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";

test(
  "user must interact with chat with Input/Output",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await configureLoopbackOpenAI(page);

    // Open Playground
    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

    await page.waitForSelector('[data-testid="input-chat-playground"]', {
      timeout: 100000,
    });

    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("Hello, how are you?");

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("button-send").click();

    await page.getByTestId("stop_building_button").waitFor({
      state: "visible",
      timeout: 30000,
    });
    await page.getByTestId("stop_building_button").waitFor({
      state: "hidden",
      timeout: 180000,
    });

    await expect(
      page.locator('[data-testid^="chat-message-User"]').first(),
    ).toHaveText("Hello, how are you?");

    await expect(
      page.locator('[data-testid^="chat-message-AI"]').first(),
    ).not.toBeEmpty();

    // close the playground (fullscreen covers the toolbar, use the close button)
    await page.getByTestId("playground-close-button").click();

    await page.getByRole("application", { name: "Chat Input node" }).click();
    await openParametersPanel(page);
    await toggleParameterOnNode(page, "sender_name");
    await closeParametersPanel(page);

    await page.getByRole("application", { name: "Chat Output node" }).click();
    await openParametersPanel(page);
    await toggleParameterOnNode(page, "sender_name");
    await closeParametersPanel(page);

    await page
      .getByTestId("popover-anchor-input-sender_name")
      .nth(0)
      .fill("TestSenderNameUser");
    await page
      .getByTestId("popover-anchor-input-sender_name")
      .nth(1)
      .fill("TestSenderNameAI");

    await page
      .getByRole("button", { name: TEXTS.playground, exact: true })
      .click();

    await page.waitForSelector('[data-testid="button-send"]', {
      timeout: 100000,
    });

    await page.getByTestId("input-chat-playground").click();
    await page.getByTestId("input-chat-playground").fill("Are you doing ok?");

    await page.getByTestId("button-send").click();

    await page.getByTestId("stop_building_button").waitFor({
      state: "visible",
      timeout: 30000,
    });
    await page.getByTestId("stop_building_button").waitFor({
      state: "hidden",
      timeout: 180000,
    });

    await expect(
      page.locator('[data-testid^="chat-message-TestSenderNameUser"]').first(),
    ).toHaveText("Are you doing ok?");

    await expect(
      page.locator('[data-testid^="chat-message-TestSenderNameAI"]').first(),
    ).not.toBeEmpty();

    await page.getByTestId("playground-close-button").click();
  },
);
