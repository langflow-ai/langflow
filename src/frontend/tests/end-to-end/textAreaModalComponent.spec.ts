import { expect, test } from "@playwright/test";

test("TextAreaModalComponent", async ({ page }) => {
  await page.goto("/");
  await page.waitForTimeout(1000);

  let modalCount = 0;
  try {
    const modalTitleElement = await page?.getByTestId("modal-title");
    if (modalTitleElement) {
      modalCount = await modalTitleElement.count();
    }
  } catch (error) {
    modalCount = 0;
  }

  while (modalCount === 0) {
    await page.getByText("New Project", { exact: true }).click();
    await page.waitForTimeout(5000);
    modalCount = await page.getByTestId("modal-title")?.count();
  }

  await page.getByTestId("blank-flow").click();
  await page.waitForTimeout(3000);
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("prompt");

  await page.waitForTimeout(1000);

  await page
    .locator('//*[@id="inputsPrompt"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTestId("prompt-input-template").click();

  await page.getByTestId("modal-prompt-input-template").fill("{text}");

  let valueBadgeOne = await page.locator('//*[@id="badge0"]').innerText();
  if (valueBadgeOne != "text") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("genericModalBtnSave").click();

  await page
    .getByTestId("textarea-text")
    .fill(
      "test test test test test test test test test test test !@#%*)( 123456789101010101010101111111111 !!!!!!!!!!",
    );

  await page.getByTestId("textarea-text-ExternalLink").click();

  await page.waitForTimeout(500);

  const value = await page.getByTestId("text-area-modal").inputValue();

  if (
    value !=
    "test test test test test test test test test test test !@#%*)( 123456789101010101010101111111111 !!!!!!!!!!"
  ) {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("text-area-modal").fill("test123123");

  await page.getByTestId("genericModalBtnSave").click();

  const valueTextArea = await page.getByTestId("textarea-text").inputValue();

  if (valueTextArea != "test123123") {
    expect(false).toBeTruthy();
  }
});
