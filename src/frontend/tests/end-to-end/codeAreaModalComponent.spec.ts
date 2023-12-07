import { expect, test } from "@playwright/test";

test("CodeAreaModalComponent", async ({ page }) => {
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("pythonfunctiontool");

  await page.waitForTimeout(2000);

  await page
    .getByTestId("toolsPythonFunctionTool")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.locator('//*[@id="code-input-0"]').click();

  let value = await page.locator('//*[@id="codeValue"]').inputValue();

  if (
    value !=
    'def python_function(text: str) -> str:    """This is a default python function that returns the input text"""    return text'
  ) {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="checkAndSaveBtn"]').click();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  await page.locator('//*[@id="showcode"]').click();
  expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showdescription"]').click();
  expect(
    await page.locator('//*[@id="showdescription"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showname"]').click();
  expect(await page.locator('//*[@id="showname"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showreturn_direct"]').click();
  expect(
    await page.locator('//*[@id="showreturn_direct"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showcode"]').click();
  expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showdescription"]').click();
  expect(
    await page.locator('//*[@id="showdescription"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showname"]').click();
  expect(await page.locator('//*[@id="showname"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showreturn_direct"]').click();
  expect(
    await page.locator('//*[@id="showreturn_direct"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showcode"]').click();
  expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showdescription"]').click();
  expect(
    await page.locator('//*[@id="showdescription"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showname"]').click();
  expect(await page.locator('//*[@id="showname"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showreturn_direct"]').click();
  expect(
    await page.locator('//*[@id="showreturn_direct"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showcode"]').click();
  expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showdescription"]').click();
  expect(
    await page.locator('//*[@id="showdescription"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showname"]').click();
  expect(await page.locator('//*[@id="showname"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showreturn_direct"]').click();
  expect(
    await page.locator('//*[@id="showreturn_direct"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showcode"]').click();
  expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="saveChangesBtn"]').click();

  const plusButtonLocator = page.locator('//*[@id="code-input-0"]');
  const elementCount = await plusButtonLocator.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("edit-button-modal").click();

    await page.locator('//*[@id="showcode"]').click();
    expect(await page.locator('//*[@id="showcode"]').isChecked()).toBeTruthy();

    await page.locator('//*[@id="code-area-edit0"]').click();

    let value = await page.locator('//*[@id="codeValue"]').inputValue();

    if (
      value !=
      'def python_function(text: str) -> str:    """This is a default python function that returns the input text"""    return text'
    ) {
      expect(false).toBeTruthy();
    }

    await page.locator('//*[@id="checkAndSaveBtn"]').click();

    await page.locator('//*[@id="saveChangesBtn"]').click();

    await page.locator('//*[@id="code-input-0"]').click();
  }
});
