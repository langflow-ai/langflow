import { expect, test } from "@playwright/test";

test("PromptTemplateComponent", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("promptTemplate");

  await page.waitForTimeout(2000);

  await page
    .locator('//*[@id="sidePromptTemplate"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.locator('//*[@id="prompt-input-4"]').click();
  await page
    .locator('//*[@id="modal-prompt-input-4"]')
    .fill("{prompt} example {prompt1}");

  let value = await page
    .locator('//*[@id="modal-prompt-input-4"]')
    .inputValue();

  if (value != "{prompt} example {prompt1}") {
    expect(false).toBeTruthy();
  }

  let valueBadgeOne = await page.locator('//*[@id="badge0"]').innerText();
  if (valueBadgeOne != "prompt") {
    expect(false).toBeTruthy();
  }

  let valueBadgeTwo = await page.locator('//*[@id="badge1"]').innerText();
  if (valueBadgeTwo != "prompt1") {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="genericModalBtnSave"]').click();

  await page.locator('//*[@id="textarea-7"]').click();
  await page.locator('//*[@id="textarea-7"]').fill("prompt_value_!@#!@#");

  value = await page.locator('//*[@id="textarea-7"]').inputValue();

  if (value != "prompt_value_!@#!@#") {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="textarea-8"]').click();
  await page
    .locator('//*[@id="textarea-8"]')
    .fill("prompt_name_test_123123!@#!@#");

  value = await page.locator('//*[@id="textarea-8"]').inputValue();

  if (value != "prompt_name_test_123123!@#!@#") {
    expect(false).toBeTruthy();
  }

  value = await page.locator('//*[@id="prompt-input-4"]').innerText();

  if (value != "{prompt} example {prompt1}") {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="editAdvancedIcon"]').click();

  value = await page.locator('//*[@id="textarea-edit-1"]').inputValue();

  if (value != "prompt_value_!@#!@#") {
    expect(false).toBeTruthy();
  }

  value = await page.locator('//*[@id="textarea-edit-2"]').inputValue();

  if (value != "prompt_name_test_123123!@#!@#") {
    expect(false).toBeTruthy();
  }

  value = await page.locator('//*[@id="prompt-area-edit0"]').innerText();

  if (value != "{prompt} example {prompt1}") {
    expect(false).toBeTruthy();
  }

  await page
    .locator('//*[@id="textarea-edit-2"]')
    .fill("prompt_edit_test_12312312321!@#$");
  await page
    .locator('//*[@id="textarea-edit-1"]')
    .fill("prompt_edit_test_44444444444!@#$");

  await page.locator('//*[@id="showtemplate"]').click();
  expect(await page.locator('//*[@id="showtemplate"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showprompt"]').click();
  expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showprompt1"]').click();
  expect(await page.locator('//*[@id="showprompt1"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showtemplate"]').click();
  expect(
    await page.locator('//*[@id="showtemplate"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showprompt"]').click();
  expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showprompt1"]').click();
  expect(await page.locator('//*[@id="showprompt1"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showtemplate"]').click();
  expect(await page.locator('//*[@id="showtemplate"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showprompt"]').click();
  expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showprompt1"]').click();
  expect(await page.locator('//*[@id="showprompt1"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showtemplate"]').click();
  expect(
    await page.locator('//*[@id="showtemplate"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showprompt"]').click();
  expect(await page.locator('//*[@id="showprompt"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="saveChangesBtn"]').click();

  const plusButtonLocator = page.locator('//*[@id="textarea-8"]');
  const elementCount = await plusButtonLocator.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page
      .locator(
        '//*[@id="react-flow-id"]/div[1]/div[1]/div[1]/div/div[2]/div/div/div[1]/div/div[1]'
      )
      .click();

    await page.locator('//*[@id="editAdvancedIcon"]').click();

    await page.locator('//*[@id="showprompt1"]').click();
    expect(
      await page.locator('//*[@id="showprompt1"]').isChecked()
    ).toBeTruthy();

    value = await page.locator('//*[@id="textarea-edit-1"]').inputValue();

    if (value != "prompt_edit_test_44444444444!@#$") {
      expect(false).toBeTruthy();
    }

    value = await page.locator('//*[@id="textarea-edit-2"]').inputValue();

    if (value != "prompt_edit_test_12312312321!@#$") {
      expect(false).toBeTruthy();
    }

    value = await page.locator('//*[@id="prompt-area-edit0"]').innerText();

    if (value != "{prompt} example {prompt1}") {
      expect(false).toBeTruthy();
    }
  }
});
