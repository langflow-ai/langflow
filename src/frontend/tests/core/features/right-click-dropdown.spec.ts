import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

import { TEXTS } from "../../utils/constants/texts";

test(
  "user can open component dropdown menu by right-clicking on nodes",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    // Start with a basic template that has multiple components
    if (await page.getByTestId("components-btn").isVisible()) {
      await page.getByTestId("side_nav_options_all-templates").click();
      await page
        .getByRole("heading", { name: TEXTS.templateBasicPrompting })
        .click();
    }

    await page.getByTestId("template-get-started-card-basic-prompting").click();

    // Wait for the flow to load. 3s was not enough on slower runners
    // (Windows CI): the sidebar input briefly resolves as visible but the
    // canvas template is still mounting, and waitForSelector observes the
    // input being re-mounted and times out. Wait for the canvas controls
    // to settle (the same gate other tests use after opening a template),
    // then verify the sidebar input.
    await page.waitForSelector('[data-testid="canvas_controls_dropdown"]', {
      timeout: 60000,
    });
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    // Test 1: Right-click on Chat Input component should open dropdown immediately (single click)
    const chatInputComponent = page.getByText(TEXTS.componentChatInput).first();

    // First, click somewhere else to ensure no component is selected
    await page.click("body", { position: { x: 100, y: 100 } });
    await page.waitForTimeout(500);

    // Single right-click on the Chat Input component should immediately open dropdown
    await chatInputComponent.click({ button: "right" });

    // Wait for and verify the dropdown menu appears immediately after single right-click
    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 2000,
    });

    // Verify the dropdown menu is visible and contains expected options
    const dropdown = page.locator('[data-testid="more-options-modal"]').first();
    await expect(dropdown).toBeVisible();

    // Verify the right-clicked component is now selected/focused (like a left-click would do)
    // The component should be visually selected and have the toolbar visible
    // Since we right-clicked, both the dropdown menu AND regular selection should be active
    const chatInputNode = page
      .locator('[data-testid="div-generic-node"]')
      .first();
    await expect(chatInputNode).toBeVisible();

    // Test 2: Verify dropdown contains expected menu items
    // Check for Save option
    const saveOption = page.getByTestId("save-button-modal");
    await expect(saveOption).toBeVisible();

    // Check for Copy option
    const copyOption = page.getByTestId("copy-button-modal").first();
    await expect(copyOption).toBeVisible();

    // Check for Delete option (should be at the bottom with red styling)
    const deleteOption = page.locator('text="Delete"').last();
    await expect(deleteOption).toBeVisible();

    // Test 3: Verify clicking on dropdown option works
    await saveOption.click();

    // Handle the save dialog if it appears
    if (await page.getByTestId("replace-button").isVisible()) {
      await page.getByTestId("replace-button").click();
    }

    // Verify the dropdown closes after selection
    await page.waitForTimeout(1000);
    await expect(saveOption).not.toBeVisible();

    // Test 4: Test right-click on different component
    const promptComponent = page.getByText("Prompt").first();

    // Right-click on the Prompt component
    await promptComponent.click({ button: "right" });

    // Verify dropdown opens for the new component
    await page.waitForSelector('[data-testid="more-options-modal"]', {
      timeout: 2000,
    });

    const newDropdown = page
      .locator('[data-testid="more-options-modal"]')
      .first();
    await expect(newDropdown).toBeVisible();
  },
);

test(
  "right-clicking inside a modal opened from a node leaves the node alone",
  { tag: ["@release", "@components"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("blank-flow").click();
    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
      timeout: 30000,
    });

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("agent");
    await page.waitForSelector('[data-testid="models_and_agentsAgent"]', {
      timeout: 5000,
    });

    await page
      .getByTestId("models_and_agentsAgent")
      .dragTo(page.locator('//*[@id="react-flow-id"]'), {
        targetPosition: { x: 400, y: 300 },
      });

    await adjustScreenView(page);

    // Open the model providers modal from the node's model field. On a
    // backend with no configured provider, ModelInput renders a "Setup
    // Provider" call-to-action that does not carry the model_model test id
    // and opens the provider manager directly (#14478). With a provider
    // configured, the model_model dropdown mounts instead and the modal
    // opens through its "Manage providers" footer button.
    const modelTrigger = page.getByTestId("model_model").first();
    const setupProviderTrigger = page
      .locator(".react-flow__node")
      .getByText("Setup Provider", { exact: true })
      .first();
    await expect(modelTrigger.or(setupProviderTrigger).first()).toBeVisible({
      timeout: 30000,
    });
    if (await setupProviderTrigger.isVisible()) {
      await setupProviderTrigger.click();
    } else {
      await modelTrigger.click();
      const manageProviders = page.getByTestId("manage-model-providers");
      if (
        await manageProviders.isVisible({ timeout: 3000 }).catch(() => false)
      ) {
        await manageProviders.click();
      }
    }

    const searchProviders = page.getByTestId("provider-search-input");
    await searchProviders.waitFor({ state: "visible", timeout: 15000 });

    // Record whether anything cancels the context menu event: the canvas
    // handler calls preventDefault(), which is what hides the browser's own
    // cut/copy/paste menu from the user.
    await page.evaluate(() => {
      (
        window as unknown as { __contextMenuPrevented: boolean[] }
      ).__contextMenuPrevented = [];
      document.addEventListener("contextmenu", (event) => {
        (
          window as unknown as { __contextMenuPrevented: boolean[] }
        ).__contextMenuPrevented.push(event.defaultPrevented);
      });
    });

    // The node may already be selected from dropping it on the canvas, so the
    // check below compares against the state right before the right-click
    // instead of assuming nothing is selected.
    const selectedNodes = page.locator(".react-flow__node.selected");
    const selectedBeforeRightClick = await selectedNodes.count();

    await searchProviders.click({ button: "right" });

    // The modal is rendered from inside the node through a portal, and React
    // bubbles events along the React tree: without a guard this right-click
    // reaches the canvas, which cancels the browser menu, opens the node
    // dropdown behind the modal and takes focus away from the search field.
    const prevented = await page.evaluate(
      () =>
        (window as unknown as { __contextMenuPrevented: boolean[] })
          .__contextMenuPrevented,
    );
    expect(prevented.length).toBeGreaterThan(0);
    expect(prevented.every((wasPrevented) => wasPrevented === false)).toBe(
      true,
    );

    // Interacting with the field first gives the app a real window to react to
    // the right-click: an auto-retrying negative assertion resolves the moment
    // its condition holds, so running it immediately would pass before a
    // dropdown could ever have rendered.
    await searchProviders.fill("openai");
    await expect(searchProviders).toHaveValue("openai");

    // "save-button-modal" lives inside the toolbar's select content, which is
    // unmounted while the dropdown is closed — the same signal the right-click
    // case above asserts positively, so a rename cannot make this check vacuous.
    await expect(page.getByTestId("save-button-modal")).toHaveCount(0);

    await expect(selectedNodes).toHaveCount(selectedBeforeRightClick);
  },
);
