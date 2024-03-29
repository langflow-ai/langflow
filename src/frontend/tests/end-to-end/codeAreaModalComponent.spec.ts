import { expect, test } from "@playwright/test";

test("CodeAreaModalComponent", async ({ page }) => {
  await page.goto("http:localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(1000);

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(1000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("pythonfunctiontool");

  await page.waitForTimeout(1000);

  await page
    .getByTestId("toolsPythonFunctionTool")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.getByTestId("div-generic-node").click();
  await page.getByTestId("code-button-modal").click();

  let value = await page.locator('//*[@id="codeValue"]').inputValue();
  const code =
    'def python_function(text: str) -> str:\n    """This is a default python function that returns the input text"""\n    return text';
  const wCode =
    'def python_function(text: str) -> st:    """This is a default python function that returns the input text"""    return text';
  const assertCode =
    'def python_function(text: str) -> str:    """This is a default python function that returns the input text"""    return text';
  await page
    .locator("#CodeEditor div")
    .filter({ hasText: "def python_function(text: str" })
    .nth(1)
    .click();
  await page.locator("textarea").press("Control+a");
  await page.locator("textarea").fill(wCode);
  await page.locator('//*[@id="checkAndSaveBtn"]').click();
  await page.waitForTimeout(1000);
  expect(
    await page.getByText("invalid syntax (<unknown>, line 1)").isVisible()
  ).toBeTruthy();
  await page.locator("textarea").press("Control+a");
  await page.locator("textarea").fill(wCode);
  await page.locator("textarea").fill(code);
  await page.locator('//*[@id="checkAndSaveBtn"]').click();
  expect(await page.getByText("Code is ready to run").isVisible()).toBeTruthy();
  await page.getByTestId("code-button-modal").click();
  expect(await page.locator('//*[@id="codeValue"]').inputValue()).toBe(
    assertCode
  );
});
