import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TEXTS } from "../../utils/constants/texts";
import { waitForNewProjectButton } from "../../utils/flow/new-project-flow";
import { openStarterProject } from "../../utils/flow/open-starter-project";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";

test(
  "should see general profile gradient",
  { tag: ["@release", "@components"] },

  async ({ page }) => {
    await awaitBootstrapTest(page, {
      skipModal: true,
      seedFlowIfEmpty: false,
    });
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await waitForNewProjectButton(page);
    await page.getByTestId("user-profile-settings").click();

    await page.getByText(TEXTS.settings).click();

    // Wait for settings page to fully load
    await page
      .waitForLoadState("networkidle", { timeout: 10000 })
      .catch(() => {});
    await page.waitForTimeout(1000);

    await expect(page.getByText("General").nth(2)).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText("Profile Picture").first()).toBeVisible();
  },
);

const FALLBACK_FIELDS = [
  "AgentQL API Key",
  "AI/ML API Key",
  "Anthropic API Key",
  "API Key",
  "Apify Token",
  "Assembly API Key",
  "Astra DB Application Token",
  "AWS Access Key ID",
];

test(
  "should interact with global variables",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page }) => {
    const randomName = Math.random().toString(36).substring(2);
    const randomName2 = Math.random().toString(36).substring(2);
    const randomName3 = Math.random().toString(36).substring(2);

    async function trySelectAvailableField(): Promise<boolean> {
      for (const fieldName of FALLBACK_FIELDS) {
        await page.getByPlaceholder("Fields").clear();
        await page.getByPlaceholder("Fields").fill(fieldName);
        await page.waitForTimeout(300);
        try {
          // [cmdk-item] targets dropdown options, not the search input
          const optionItem = page.locator(
            `[cmdk-item]:has-text("${fieldName}")`,
          );
          await optionItem.waitFor({ state: "visible", timeout: 2000 });
          await optionItem.click();
          return true;
        } catch {
          continue;
        }
      }
      return false;
    }

    await awaitBootstrapTest(page, {
      skipModal: true,
      seedFlowIfEmpty: false,
    });
    await page.getByTestId("user-profile-settings").click();
    await page.getByText(TEXTS.settings).click();
    await page.getByText("Global Variables").click();
    await expect(
      page.getByText("Global Variables", { exact: true }).nth(1),
    ).toBeVisible({ timeout: 10000 });
    await page.getByText("Add New").click();
    await page.getByPlaceholder(TEXTS.placeholderVariableName).fill(randomName);
    await expect(page.getByText("Generic", { exact: true }).last()).toBeVisible(
      { timeout: 10000 },
    );
    await page.getByText("Generic", { exact: true }).last().click();

    await page
      .getByPlaceholder("Enter a value for the variable...")
      .fill("testtesttesttesttesttesttesttest");
    await page.getByTestId("popover-anchor-apply-to-fields").click();

    await page.getByPlaceholder("Fields").first().waitFor({
      state: "visible",
      timeout: 30000,
    });

    const fieldSelected = await trySelectAvailableField();
    expect(fieldSelected).toBe(true);

    await page.keyboard.press("Escape");

    await page
      .getByText("Save Variable", { exact: true })
      .dispatchEvent("click");

    await page.waitForTimeout(500);

    await expect(page.getByText(randomName).last()).toBeVisible({
      timeout: 10000,
    });

    await page.locator(`.ag-cell:has-text("${randomName}")`).first().click();

    await page.getByPlaceholder(TEXTS.placeholderVariableName).waitFor({
      state: "visible",
      timeout: 30000,
    });

    await page
      .getByPlaceholder(TEXTS.placeholderVariableName)
      .fill(randomName2);

    await page
      .getByText("Update Variable", { exact: true })
      .last()
      .dispatchEvent("click");
    await page.waitForTimeout(500);

    await expect(page.getByText(randomName2).last()).toBeVisible({
      timeout: 10000,
    });

    await page.waitForTimeout(500);

    await page.locator(`.ag-cell:has-text("${randomName2}")`).first().click();

    await page.getByPlaceholder(TEXTS.placeholderVariableName).waitFor({
      state: "visible",
      timeout: 30000,
    });

    await page
      .getByPlaceholder(TEXTS.placeholderVariableName)
      .fill(randomName3);

    await page
      .getByText("Update Variable", { exact: true })
      .last()
      .dispatchEvent("click");
    await page.waitForTimeout(500);

    await expect(page.getByText(randomName3).last()).toBeVisible({
      timeout: 10000,
    });

    await page.waitForTimeout(3000);
    await page.locator(".ag-input-field-input").first().click();
    await page.getByTestId("icon-Trash2").click();
    await expect(page.getByText("No data available")).toBeVisible({
      timeout: 10000,
    });
  },
);

test("should see shortcuts", { tag: ["@release"] }, async ({ page }) => {
  await awaitBootstrapTest(page, {
    skipModal: true,
    seedFlowIfEmpty: false,
  });
  await page.waitForSelector('[data-testid="mainpage_title"]', {
    timeout: 30000,
  });

  await waitForNewProjectButton(page);
  await page.getByTestId("user-profile-settings").click();

  await page.getByText(TEXTS.settings).click();

  // Wait for settings page to fully load
  await page
    .waitForLoadState("networkidle", { timeout: 10000 })
    .catch(() => {});
  await page.waitForTimeout(1000);

  await expect(page.getByText("General").nth(2)).toBeVisible({
    timeout: 10000,
  });
  await page.getByText("Shortcuts").nth(0).click();

  // Wait for shortcuts section to load
  await page.waitForTimeout(1000);

  await expect(page.getByText("Shortcuts", { exact: true }).nth(1)).toBeVisible(
    { timeout: 10000 },
  );
  //TODO Do not seem to be in the list, is it a product change?
  // await expect(page.getByText("Controls", { exact: true })).toBeVisible({
  //   timeout: 10000,
  // });

  await expect(
    page.getByText("Search Components on Sidebar", { exact: true }),
  ).toBeVisible({ timeout: 10000 });

  await expect(page.getByText("Minimize", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Code", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Copy", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Duplicate", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Docs", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Changes Save", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText(TEXTS.delete, { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Open Playground", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText("Undo", { exact: true })).toBeVisible({
    timeout: 10000,
  });

  await page.mouse.wheel(0, 10000);

  await expect(page.getByText("Redo", { exact: true }).last()).toBeVisible({
    timeout: 10000,
  });

  await expect(
    page.getByText("Redo (alternative)", { exact: true }).last(),
  ).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Group").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Cut").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Paste").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("API").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Download").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Update").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Freeze").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Flow Share").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Play").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Output Inspection").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Tool Mode").last()).toBeVisible({
    timeout: 10000,
  });

  await expect(page.getByText("Toggle Sidebar").last()).toBeVisible({
    timeout: 10000,
  });
});

test(
  "should interact with API Keys",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await page.addInitScript(() => {
      const clipboardWrites: string[] = [];
      Object.defineProperty(window, "__playwrightClipboardWrites", {
        configurable: true,
        value: clipboardWrites,
      });
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: {
          writeText: async (value: string) => {
            clipboardWrites.push(value);
          },
        },
      });
    });

    await awaitBootstrapTest(page, {
      skipModal: true,
      seedFlowIfEmpty: false,
    });
    await page.getByTestId("user-profile-settings").click();
    await page.getByText(TEXTS.settings).click();

    const langflowApiNavItem = page.getByText("Langflow API").first();
    await expect(langflowApiNavItem).toBeVisible({ timeout: 10000 });
    await langflowApiNavItem.click();

    await expect(
      page.getByText("Langflow API Keys", { exact: true }).nth(1),
    ).toBeVisible({ timeout: 10000 });
    await page.getByText("Add New").click();
    await expect(page.getByPlaceholder("My API Key")).toBeVisible({
      timeout: 10000,
    });

    const randomName = Math.random().toString(36).substring(2);

    await page.getByPlaceholder("My API Key").fill(randomName);
    await page.getByText("Generate API Key", { exact: true }).click();

    await expect(page.getByText("Please save")).toBeVisible({
      timeout: 30000,
    });
    const generatedKeyInput = page.getByTestId("api-key-input");
    await expect(generatedKeyInput).toHaveValue(/\S+/, { timeout: 30000 });

    await page.getByTestId("btn-copy-api-key").click();

    await expect(
      page.getByText("API Key copied!", { exact: true }),
    ).toBeVisible();

    const clipboardCapture = await page.evaluate(() => {
      const renderedKey = document.querySelector<HTMLInputElement>(
        '[data-testid="api-key-input"]',
      )?.value;
      const writes = (
        window as Window & { __playwrightClipboardWrites?: string[] }
      ).__playwrightClipboardWrites;

      return {
        copiedRenderedKey:
          Boolean(renderedKey) &&
          writes?.length === 1 &&
          writes[0] === renderedKey,
        writeCount: writes?.length ?? 0,
      };
    });
    expect(clipboardCapture).toEqual({
      copiedRenderedKey: true,
      writeCount: 1,
    });

    await page.getByTestId("secret_key_modal_submit_button").click();

    await page.mouse.wheel(0, 10000);

    await expect(page.getByText(randomName)).toBeVisible({ timeout: 10000 });
  },
);

test(
  "should navigate back to flow from global variables",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await openStarterProject(page, TEXTS.templateBasicPrompting, {
      skipBootstrap: true,
    });

    // Now navigate to user settings
    await page.getByTestId("user-profile-settings").click();
    await page.getByTestId("menu_settings_button").click();

    // Verify we're on the settings page
    await expect(page.getByText("General").nth(2)).toBeVisible({
      timeout: 15000,
    });

    // Navigate to Global Variables
    await page.getByText("Global Variables").click();
    await expect(
      page.getByText("Global Variables", { exact: true }).nth(1),
    ).toBeVisible({ timeout: 10000 });

    // Click the back button - this should take us back to the flow, not to the main settings page
    await page.getByTestId("back_page_button").click();

    // Verify we're back on the flow page, not the settings main page.
    // Re-rendering the flow canvas after leaving settings is slow on busy
    // (e.g. Windows) CI runners, so allow a generous window before asserting.
    await waitForFlowEditorReady(page);

    // Additional verification that we're on the flow page
    expect(page.url()).toMatch(/\/flow\//);

    // Verify we can see flow-specific elements
    await expect(page.getByTestId("sidebar-search-input")).toBeVisible();
  },
);
