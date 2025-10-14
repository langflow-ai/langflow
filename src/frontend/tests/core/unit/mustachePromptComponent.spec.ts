import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

/**
 * Helper function to add a Prompt component to the canvas
 */
async function addPromptComponent(page: any) {
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("prompt");
  await page.waitForSelector('[data-testid="processingPrompt Template"]', {
    timeout: 3000,
  });

  await page
    .locator('//*[@id="processingPrompt Template"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await adjustScreenView(page);
}

/**
 * Helper function to switch mode between {variable} and {{variable}}
 */
async function switchMode(page: any, mode: "{variable}" | "{{variable}}") {
  const modeText = mode === "{variable}" ? "{variable}" : "{{variable}}";
  await page.getByText(modeText).click();
  // Wait for mode switch to complete
  await page.waitForTimeout(500);
}

/**
 * Helper function to verify prompt variables in the modal
 */
async function verifyPromptVariables(
  page: any,
  template: string,
  expectedVars: string[],
  isFirstTime = true,
) {
  await page.getByTestId("promptarea_prompt_template").click();

  if (isFirstTime) {
    await page.getByTestId("modal-promptarea_prompt_template").fill(template);
  } else {
    await page.getByRole("dialog").getByTestId("edit-prompt-sanitized").click();
    await page.getByTestId("modal-promptarea_prompt_template").fill(template);
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

/**
 * Helper function to check if a field exists in the component
 */
async function checkFieldExists(
  page: any,
  fieldName: string,
): Promise<boolean> {
  try {
    const field = await page.getByTestId(`textarea_str_${fieldName}`);
    return await field.isVisible({ timeout: 1000 });
  } catch {
    return false;
  }
}

test(
  "Mustache Prompt - Mode Switching",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await addPromptComponent(page);

    // Start with f-string mode and add a variable
    await verifyPromptVariables(
      page,
      "Hello {fstring_var}!",
      ["fstring_var"],
      true,
    );

    // Verify the f-string field exists
    const fstringFieldExists = await checkFieldExists(page, "fstring_var");
    expect(fstringFieldExists).toBeTruthy();

    // Switch to mustache mode
    await switchMode(page, "{{variable}}");

    // The f-string field should be removed after mode switch
    await page.waitForTimeout(1000);
    const fstringFieldAfterSwitch = await checkFieldExists(page, "fstring_var");
    expect(fstringFieldAfterSwitch).toBeFalsy();

    // Add a mustache variable
    await page.getByTestId("promptarea_prompt_template").click();
    await page.getByRole("dialog").getByTestId("edit-prompt-sanitized").click();
    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("Hello {{mustache_var}}!");

    // Verify mustache variable badge
    const badgeText = await page.locator('//*[@id="badge0"]').innerText();
    expect(badgeText).toBe("mustache_var");

    await page.getByTestId("genericModalBtnSave").click();

    // Verify the mustache field exists
    const mustacheFieldExists = await checkFieldExists(page, "mustache_var");
    expect(mustacheFieldExists).toBeTruthy();

    // Switch back to f-string mode
    await switchMode(page, "{variable}");

    // The mustache field should be removed after mode switch
    await page.waitForTimeout(1000);
    const mustacheFieldAfterSwitch = await checkFieldExists(
      page,
      "mustache_var",
    );
    expect(mustacheFieldAfterSwitch).toBeFalsy();
  },
);

test(
  "Mustache Prompt - Mixed Syntax Handling",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await addPromptComponent(page);

    // Add template with BOTH syntaxes
    const mixedTemplate = "F-string: {fstring_var}, Mustache: {{mustache_var}}";

    // In f-string mode, only f-string variables should create fields
    await page.getByTestId("promptarea_prompt_template").click();
    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill(mixedTemplate);

    // Should only show fstring_var badge
    const badgeText = await page.locator('//*[@id="badge0"]').innerText();
    expect(badgeText).toBe("fstring_var");

    // Should NOT show mustache_var badge
    const extraBadge = await page
      .locator('//*[@id="badge1"]')
      .isVisible()
      .catch(() => false);
    expect(extraBadge).toBeFalsy();

    await page.getByTestId("genericModalBtnSave").click();

    // Only fstring_var field should exist
    const fstringFieldExists = await checkFieldExists(page, "fstring_var");
    expect(fstringFieldExists).toBeTruthy();

    const mustacheFieldExists = await checkFieldExists(page, "mustache_var");
    expect(mustacheFieldExists).toBeFalsy();

    // Now switch to mustache mode
    await switchMode(page, "{{variable}}");
    await page.waitForTimeout(1000);

    // Open modal again with same mixed template
    await page.getByTestId("promptarea_prompt_template").click();
    await page.getByRole("dialog").getByTestId("edit-prompt-sanitized").click();
    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill(mixedTemplate);

    // Should only show mustache_var badge
    const mustacheBadgeText = await page
      .locator('//*[@id="badge0"]')
      .innerText();
    expect(mustacheBadgeText).toBe("mustache_var");

    await page.getByTestId("genericModalBtnSave").click();

    // Only mustache_var field should exist now
    const fstringFieldAfter = await checkFieldExists(page, "fstring_var");
    expect(fstringFieldAfter).toBeFalsy();

    const mustacheFieldAfter = await checkFieldExists(page, "mustache_var");
    expect(mustacheFieldAfter).toBeTruthy();
  },
);

test(
  "Mustache Prompt - Validation Errors Don't Break Component",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await addPromptComponent(page);

    // Switch to mustache mode
    await switchMode(page, "{{variable}}");

    // Try to add a variable with invalid syntax (space in name)
    await page.getByTestId("promptarea_prompt_template").click();
    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("Invalid: {{mustache var}}");

    await page.getByTestId("genericModalBtnSave").click();

    // Should show error alert
    const errorAlert = await page
      .getByText(/Invalid mustache variable/i)
      .isVisible({ timeout: 3000 });
    expect(errorAlert).toBeTruthy();

    // Component should still be functional - close error and try again
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);

    // Fix the syntax
    await page.getByTestId("promptarea_prompt_template").click();
    await page.getByRole("dialog").getByTestId("edit-prompt-sanitized").click();
    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("Valid: {{mustache_var}}");

    const badgeText = await page.locator('//*[@id="badge0"]').innerText();
    expect(badgeText).toBe("mustache_var");

    await page.getByTestId("genericModalBtnSave").click();

    // Should succeed and create field
    const mustacheFieldExists = await checkFieldExists(page, "mustache_var");
    expect(mustacheFieldExists).toBeTruthy();
  },
);

test(
  "Mustache Prompt - Mode Switch Cleans Up Old Fields",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await addPromptComponent(page);

    // Add multiple f-string variables
    await verifyPromptVariables(
      page,
      "{var1} and {var2} and {var3}",
      ["var1", "var2", "var3"],
      true,
    );

    // Verify all fields exist
    expect(await checkFieldExists(page, "var1")).toBeTruthy();
    expect(await checkFieldExists(page, "var2")).toBeTruthy();
    expect(await checkFieldExists(page, "var3")).toBeTruthy();

    // Switch to mustache mode
    await switchMode(page, "{{variable}}");
    await page.waitForTimeout(1000);

    // All f-string fields should be removed
    expect(await checkFieldExists(page, "var1")).toBeFalsy();
    expect(await checkFieldExists(page, "var2")).toBeFalsy();
    expect(await checkFieldExists(page, "var3")).toBeFalsy();

    // Add mustache variables
    await page.getByTestId("promptarea_prompt_template").click();
    await page.getByRole("dialog").getByTestId("edit-prompt-sanitized").click();
    await page
      .getByTestId("modal-promptarea_prompt_template")
      .fill("{{new_var1}} and {{new_var2}}");

    await page.getByTestId("genericModalBtnSave").click();

    // New mustache fields should exist
    expect(await checkFieldExists(page, "new_var1")).toBeTruthy();
    expect(await checkFieldExists(page, "new_var2")).toBeTruthy();

    // Old f-string fields should still not exist
    expect(await checkFieldExists(page, "var1")).toBeFalsy();
    expect(await checkFieldExists(page, "var2")).toBeFalsy();
    expect(await checkFieldExists(page, "var3")).toBeFalsy();
  },
);

test(
  "Mustache Prompt - No Handles Shown",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await addPromptComponent(page);

    // Add a mustache variable
    await switchMode(page, "{{variable}}");
    await verifyPromptVariables(page, "Test {{my_var}}", ["my_var"], true);

    // The mustache field should not have a connection handle
    // (This tests that "mustache" was added to LANGFLOW_SUPPORTED_TYPES)
    const handleSelector = `[data-testid="handle-my_var-shownode-left"]`;
    const handleExists = await page
      .locator(handleSelector)
      .isVisible({ timeout: 1000 })
      .catch(() => false);

    // Handle should NOT exist for mustache prompt fields
    expect(handleExists).toBeFalsy();
  },
);
