import type { Page } from "@playwright/test";
import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

// Helper function to verify prompt variables
async function verifyPromptVariables(
  page: Page,
  template: string,
  expectedVars: string[],
  isFirstTime = true,
) {
  await page.getByTestId("promptarea_prompt_template").click();

  // Use different selectors based on whether this is the first time or a subsequent edit
  if (isFirstTime) {
    await page.getByTestId("modal-promptarea_prompt_template").fill(template);

    // Verify the template is set correctly
    const value = await page
      .getByTestId("modal-promptarea_prompt_template")
      .inputValue();
    expect(value).toBe(template);
  } else {
    // For subsequent edits, we need to click the edit button first
    await page.getByRole("dialog").getByTestId("edit-prompt-sanitized").click();
    await page.getByTestId("modal-promptarea_prompt_template").fill(template);

    // Verify the template is set correctly
    const value = await page
      .getByTestId("modal-promptarea_prompt_template")
      .inputValue();
    expect(value).toBe(template);
  }

  // Verify each expected variable has a badge
  for (let i = 0; i < expectedVars.length; i++) {
    const badgeText = await page.locator(`//*[@id="badge${i}"]`).innerText();
    expect(badgeText).toBe(expectedVars[i]);
  }

  // Verify no extra badges exist
  const extraBadge = await page
    .locator(`//*[@id="badge${expectedVars.length}"]`)
    .isVisible()
    .catch(() => false);
  expect(extraBadge).toBeFalsy();

  await page.getByTestId("genericModalBtnSave").click();
}

test(
  "PromptTemplateComponent - Variable Extraction",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("prompt");
    await page.waitForSelector(
      '[data-testid="models_and_agentsPrompt Template"]',
      {
        timeout: 3000,
      },
    );

    await page
      .locator('//*[@id="models_and_agentsPrompt Template"]')
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    // Test basic variable extraction (first time)
    await verifyPromptVariables(page, "Hello {name}!", ["name"], true);

    // Test multiple variables (subsequent edit)
    await verifyPromptVariables(
      page,
      "Hi {name}, you are {age} years old",
      ["name", "age"],
      false,
    );

    // Test duplicate variables (should only show once)
    await verifyPromptVariables(
      page,
      "Hello {name}! How are you {name}?",
      ["name"],
      false,
    );

    // Test escaped variables with {{}}
    await verifyPromptVariables(
      page,
      "Escaped {{not_a_var}} but {real_var} works",
      ["real_var"],
      false,
    );

    // Test complex template
    await verifyPromptVariables(
      page,
      "Hello {name}! Your score is {{4 + 5}}, age: {age}",
      ["name", "age"],
      false,
    );

    // Test multiline template
    await verifyPromptVariables(
      page,
      `Multi-line with {var1}
      and {var2} plus
      {var3} at the end`,
      ["var1", "var2", "var3"],
      false,
    );

    // Final verification - check that the template persists
    await page.getByTestId("div-generic-node").click();
    await page.getByTestId("edit-button-modal").last().click();

    const savedTemplate = await page
      .locator('//*[@id="promptarea_prompt_edit_template"]')
      .innerText();
    expect(savedTemplate).toBe(
      "Multi-line with {var1}\n      and {var2} plus\n      {var3} at the end",
    );

    // Close the final modal
    await page.getByText("Close").last().click();
  },
);

test(
  "PromptTemplateComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("prompt");

    await page.waitForSelector(
      '[data-testid="models_and_agentsPrompt Template"]',
      {
        timeout: 3000,
      },
    );

    await page
      .locator('//*[@id="models_and_agentsPrompt Template"]')
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);
    await page.getByTestId("promptarea_prompt_template").click();

    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("{prompt} example {prompt1}");

    let value = await page
      .getByTestId("modal-promptarea_prompt_template")
      .inputValue();

    if (value != "{prompt} example {prompt1}") {
      expect(false).toBeTruthy();
    }

    const valueBadgeOne = await page.locator('//*[@id="badge0"]').innerText();
    if (valueBadgeOne != "prompt") {
      expect(false).toBeTruthy();
    }

    const valueBadgeTwo = await page.locator('//*[@id="badge1"]').innerText();
    if (valueBadgeTwo != "prompt1") {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("genericModalBtnSave").click();

    await page.getByTestId("textarea_str_prompt").click();
    await page.getByTestId("textarea_str_prompt").fill("prompt_value_!@#!@#");

    value = await page.getByTestId("textarea_str_prompt").inputValue();

    if (value != "prompt_value_!@#!@#") {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("save-button-modal").click();

    const replace = await page.getByTestId("replace-button").isVisible();

    if (replace) {
      await page.getByTestId("replace-button").click();
    }

    await page.getByTestId("textarea_str_prompt1").click();
    await page
      .getByTestId("textarea_str_prompt1")
      .fill("prompt_name_test_123123!@#!@#");

    value = await page.getByTestId("textarea_str_prompt1").inputValue();

    if (value != "prompt_name_test_123123!@#!@#") {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("edit-button-modal").last().click();

    value =
      (await page
        .locator('//*[@id="textarea_str_edit_prompt"]')
        .inputValue()) ?? "";

    if (value != "prompt_value_!@#!@#") {
      expect(false).toBeTruthy();
    }

    value =
      (await page
        .locator('//*[@id="textarea_str_edit_prompt1"]')
        .inputValue()) ?? "";

    if (value != "prompt_name_test_123123!@#!@#") {
      expect(false).toBeTruthy();
    }

    value = await page
      .locator('//*[@id="promptarea_prompt_edit_template"]')
      .innerText();

    if (value != "{prompt} example {prompt1}") {
      expect(false).toBeTruthy();
    }

    await page
      .getByTestId(
        "button_open_text_area_modal_textarea_str_edit_prompt1_advanced",
      )
      .click();
    await page
      .getByTestId("text-area-modal")
      .fill("prompt_edit_test_12312312321!@#$");

    await page.getByText("Finish Editing", { exact: true }).click();

    await page
      .getByTestId(
        "button_open_text_area_modal_textarea_str_edit_prompt_advanced",
      )
      .nth(0)
      .click();
    await page
      .getByTestId("text-area-modal")
      .fill("prompt_edit_test_44444444444!@#$");

    await page.getByText("Finish Editing", { exact: true }).click();

    await page.locator('//*[@id="showtemplate"]').click();
    expect(
      await page.locator('//*[@id="showtemplate"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showprompt"]').click();
    expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeFalsy();

    await page.locator('//*[@id="showprompt1"]').click();
    expect(
      await page.locator('//*[@id="showprompt1"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showtemplate"]').click();
    expect(
      await page.locator('//*[@id="showtemplate"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showprompt"]').click();
    expect(
      await page.locator('//*[@id="showprompt"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showprompt1"]').click();
    expect(
      await page.locator('//*[@id="showprompt1"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showtemplate"]').click();
    expect(
      await page.locator('//*[@id="showtemplate"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showprompt"]').click();
    expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeFalsy();

    await page.locator('//*[@id="showprompt1"]').click();
    expect(
      await page.locator('//*[@id="showprompt1"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showtemplate"]').click();
    expect(
      await page.locator('//*[@id="showtemplate"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showprompt"]').click();
    expect(
      await page.locator('//*[@id="showprompt"]').isChecked(),
    ).toBeTruthy();

    await page.getByText("Close").last().click();
    await adjustScreenView(page, { numberOfZoomOut: 2 });

    await page.getByTestId("edit-button-modal").last().click();

    await page.locator('//*[@id="showprompt1"]').click();
    expect(
      await page.locator('//*[@id="showprompt1"]').isChecked(),
    ).toBeTruthy();

    value =
      (await page
        .locator('//*[@id="textarea_str_edit_prompt"]')
        .inputValue()) ?? "";

    if (value != "prompt_edit_test_44444444444!@#$") {
      expect(false).toBeTruthy();
    }

    value =
      (await page
        .locator('//*[@id="textarea_str_edit_prompt1"]')
        .inputValue()) ?? "";

    if (value != "prompt_edit_test_12312312321!@#$") {
      expect(false).toBeTruthy();
    }

    value = await page
      .locator('//*[@id="promptarea_prompt_edit_template"]')
      .innerText();

    if (value != "{prompt} example {prompt1}") {
      expect(false).toBeTruthy();
    }
  },
);

test(
  "PromptTemplateComponent - Double Brackets Variable Extraction",
  { tag: ["@release", "@workspace"], timeout: 60000 },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("prompt");

    await page.waitForSelector(
      '[data-testid="models_and_agentsPrompt Template"]',
      {
        timeout: 3000,
      },
    );

    await page
      .locator('//*[@id="models_and_agentsPrompt Template"]')
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    // Wait for the node to appear
    await page.waitForSelector('[data-testid="div-generic-node"]', {
      timeout: 5000,
    });

    // Click on the node to select it
    await page.getByTestId("div-generic-node").click();

    // Wait for and click the edit button
    await page.waitForSelector('[data-testid="edit-button-modal"]', {
      timeout: 5000,
    });
    await page.getByTestId("edit-button-modal").last().click();

    // Wait for the modal to open and the toggle to be visible
    await page.waitForSelector(
      '[data-testid="toggle_bool_edit_use_double_brackets"]',
      {
        timeout: 5000,
      },
    );

    // Enable the "Use Double Brackets" toggle in the modal
    await page.getByTestId("toggle_bool_edit_use_double_brackets").click();

    // Verify the toggle is now checked
    expect(
      await page
        .getByTestId("toggle_bool_edit_use_double_brackets")
        .isChecked(),
    ).toBeTruthy();

    // Close the modal
    await page.getByText("Close").last().click();

    // Now test double bracket variable extraction - click the mustache prompt button
    await page.waitForSelector(
      '[data-testid="button_open_mustache_prompt_modal"]',
      {
        timeout: 5000,
      },
    );
    await page.getByTestId("button_open_mustache_prompt_modal").click();

    // Wait for the prompt modal textarea (mustache modal uses different testid pattern)
    const mustacheTextareaId = "modal-mustachepromptarea_mustache_template";
    await page.waitForSelector(`[data-testid="${mustacheTextareaId}"]`, {
      timeout: 5000,
    });

    await page.getByTestId(mustacheTextareaId).fill("Hello {{name}}!");

    let value = await page.getByTestId(mustacheTextareaId).inputValue();

    expect(value).toBe("Hello {{name}}!");

    // Verify the variable badge shows "name"
    await page.waitForSelector('//*[@id="badge0"]', { timeout: 5000 });
    const valueBadgeOne = await page.locator('//*[@id="badge0"]').innerText();
    expect(valueBadgeOne).toBe("name");

    await page.getByTestId("genericModalBtnSave").click();

    // Wait for modal to close and variable input to appear
    await page.waitForSelector('[data-testid="textarea_str_name"]', {
      timeout: 5000,
    });

    // Verify the input field for the variable was created
    await page.getByTestId("textarea_str_name").click();
    await page.getByTestId("textarea_str_name").fill("World");

    value = await page.getByTestId("textarea_str_name").inputValue();
    expect(value).toBe("World");
  },
);

test(
  "PromptTemplateComponent - Double Brackets Multiple Variables",
  { tag: ["@release", "@workspace"], timeout: 60000 },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();
    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("prompt");

    await page.waitForSelector(
      '[data-testid="models_and_agentsPrompt Template"]',
      {
        timeout: 3000,
      },
    );

    await page
      .locator('//*[@id="models_and_agentsPrompt Template"]')
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await adjustScreenView(page);

    // Wait for the node to appear
    await page.waitForSelector('[data-testid="div-generic-node"]', {
      timeout: 5000,
    });

    // Click on the node to select it
    await page.getByTestId("div-generic-node").click();

    // Wait for and click the edit button
    await page.waitForSelector('[data-testid="edit-button-modal"]', {
      timeout: 5000,
    });
    await page.getByTestId("edit-button-modal").last().click();

    // Wait for the modal to open and the toggle to be visible
    await page.waitForSelector(
      '[data-testid="toggle_bool_edit_use_double_brackets"]',
      {
        timeout: 5000,
      },
    );

    // Enable the "Use Double Brackets" toggle in the modal
    await page.getByTestId("toggle_bool_edit_use_double_brackets").click();

    // Verify the toggle is now checked
    expect(
      await page
        .getByTestId("toggle_bool_edit_use_double_brackets")
        .isChecked(),
    ).toBeTruthy();

    // Close the modal
    await page.getByText("Close").last().click();

    // Test multiple double bracket variables - click the mustache prompt button
    await page.waitForSelector(
      '[data-testid="button_open_mustache_prompt_modal"]',
      {
        timeout: 5000,
      },
    );
    await page.getByTestId("button_open_mustache_prompt_modal").click();

    // Wait for the prompt modal textarea (mustache modal uses different testid pattern)
    const mustacheTextareaId = "modal-mustachepromptarea_mustache_template";
    await page.waitForSelector(`[data-testid="${mustacheTextareaId}"]`, {
      timeout: 5000,
    });

    await page
      .getByTestId(mustacheTextareaId)
      .fill("{{greeting}} {{name}}! You are {{age}} years old.");

    const value = await page.getByTestId(mustacheTextareaId).inputValue();

    expect(value).toBe("{{greeting}} {{name}}! You are {{age}} years old.");

    // Verify all variable badges
    await page.waitForSelector('//*[@id="badge0"]', { timeout: 5000 });
    const badgeGreeting = await page.locator('//*[@id="badge0"]').innerText();
    expect(badgeGreeting).toBe("greeting");

    const badgeName = await page.locator('//*[@id="badge1"]').innerText();
    expect(badgeName).toBe("name");

    const badgeAge = await page.locator('//*[@id="badge2"]').innerText();
    expect(badgeAge).toBe("age");

    // Verify no extra badges
    const extraBadge = await page
      .locator('//*[@id="badge3"]')
      .isVisible()
      .catch(() => false);
    expect(extraBadge).toBeFalsy();

    await page.getByTestId("genericModalBtnSave").click();

    // Wait for modal to close and verify input fields for all variables were created
    await page.waitForSelector('[data-testid="textarea_str_greeting"]', {
      timeout: 5000,
    });
    await page.waitForSelector('[data-testid="textarea_str_name"]', {
      timeout: 5000,
    });
    await page.waitForSelector('[data-testid="textarea_str_age"]', {
      timeout: 5000,
    });

    // Fill in the variable inputs and verify they work
    await page.getByTestId("textarea_str_greeting").fill("Hello");
    expect(await page.getByTestId("textarea_str_greeting").inputValue()).toBe(
      "Hello",
    );

    await page.getByTestId("textarea_str_name").fill("Alice");
    expect(await page.getByTestId("textarea_str_name").inputValue()).toBe(
      "Alice",
    );

    await page.getByTestId("textarea_str_age").fill("25");
    expect(await page.getByTestId("textarea_str_age").inputValue()).toBe("25");
  },
);
