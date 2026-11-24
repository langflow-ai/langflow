import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { configureLoopbackOpenAI } from "../../utils/configure-loopback-openai";
import { TID } from "../../utils/constants/testIds";
import { TIMEOUTS } from "../../utils/constants/timeouts";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { sendPlaygroundMessage } from "../../utils/playground/send-playground-message";
import { seedLoopbackProvider } from "../../utils/seed-loopback-provider";

const ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929";

async function mockAnthropicModelCatalog(page: Page) {
  await page.route(
    (url) => url.pathname === "/api/v1/models/enabled_models",
    async (route) => {
      await route.fulfill({
        json: {
          enabled_models: {
            Anthropic: { [ANTHROPIC_MODEL]: true },
            OpenAI: { "gpt-4o-mini": true },
          },
        },
      });
    },
  );
  await page.route(
    (url) => url.pathname === "/api/v1/models",
    async (route) => {
      await route.fulfill({
        json: [
          {
            provider: "Anthropic",
            icon: "Anthropic",
            is_enabled: true,
            is_configured: true,
            models: [
              {
                model_name: ANTHROPIC_MODEL,
                metadata: { model_type: "llm", tool_calling: true },
              },
            ],
          },
          {
            provider: "OpenAI",
            icon: "OpenAI",
            is_enabled: true,
            is_configured: true,
            models: [
              {
                model_name: "gpt-4o-mini",
                metadata: { model_type: "llm", tool_calling: true },
              },
            ],
          },
        ],
      });
    },
  );
}

test(
  "user can select Anthropic before running Simple Agent through the loopback provider",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await seedLoopbackProvider(page);
    await mockAnthropicModelCatalog(page);
    await openStarterProject(page, "Simple Agent");

    const modelDropdown = page.getByTestId(TID.modelModel);
    await modelDropdown.click();
    const anthropicOption = page.getByTestId(
      `Anthropic-${ANTHROPIC_MODEL}-option`,
    );
    await anthropicOption.scrollIntoViewIfNeeded();
    await anthropicOption.click();
    await expect(modelDropdown).toContainText(ANTHROPIC_MODEL);

    // The assertion above covers current ModelInput catalog selection. Runtime
    // behavior is intentionally isolated from Anthropic credentials/network by
    // switching the saved flow to the local OpenAI-compatible fixture below.
    await configureLoopbackOpenAI(page);

    await page.getByTestId(TID.playgroundBtnFlowIo).click();
    await sendPlaygroundMessage(page, "Describe deterministic CI in one line.");

    await expect(page.locator(".markdown.prose").last()).toContainText(/\S/, {
      timeout: TIMEOUTS.buildComplete,
    });
  },
);
