import { expect, test } from "@playwright/test";

test("InputListComponent", async ({ page }) => {
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
  await page.waitForSelector('[data-testid="extended-disclosure"]', {
    timeout: 30000,
  });
  await page.getByTestId("extended-disclosure").click();
  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("url");

  await page.waitForTimeout(1000);
  await page
    .getByTestId("dataURL")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTitle("fit view").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();
  await page.getByTitle("zoom out").click();

  await page.getByTestId("input-list-input_urls-0").fill("test test test test");

  await page.getByTestId("input-list-plus-btn_urls-0").click();

  await page.getByTestId("input-list-plus-btn_urls-0").click();

  await page
    .getByTestId("input-list-input_urls-1")
    .fill("test1 test1 test1 test1");

  await page
    .getByTestId("input-list-input_urls-2")
    .fill("test2 test2 test2 test2");

  await page.getByTestId("div-generic-node").click();
  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  const value0 = await page
    .getByTestId("input-list-input-edit_urls-0")
    .inputValue();
  const value1 = await page
    .getByTestId("input-list-input-edit_urls-1")
    .inputValue();

  const value2 = await page
    .getByTestId("input-list-input-edit_urls-2")
    .inputValue();

  if (
    value0 !== "test test test test" ||
    value1 !== "test1 test1 test1 test1" ||
    value2 !== "test2 test2 test2 test2"
  ) {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("input-list-minus-btn-edit_urls-1").click();

  const plusButtonLocator = page.getByTestId(
    "input-list-minus-btn-edit_urls-1",
  );
  const elementCount = await plusButtonLocator?.count();

  if (elementCount > 1) {
    expect(false).toBeTruthy();
  }

  await page.getByText("Close").last().click();

  await page.getByTestId("input-list-minus-btn_urls-2").isHidden();

  await page.getByTestId("input-list-plus-btn_urls-0").click();
  await page.getByTestId("input-list-plus-btn_urls-0").click();

  await page.getByTestId("input-list-input_urls-0").fill("test test test test");
  await page
    .getByTestId("input-list-input_urls-1")
    .fill("test1 test1 test1 test1");
  await page
    .getByTestId("input-list-input_urls-2")
    .fill("test2 test2 test2 test2");
  await page
    .getByTestId("input-list-input_urls-3")
    .fill("test3 test3 test3 test3");

  await page.getByTestId("div-generic-node").click();
  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  const value0Edit = await page
    .getByTestId("input-list-input-edit_urls-0")
    .inputValue();
  const value1Edit = await page
    .getByTestId("input-list-input-edit_urls-1")
    .inputValue();
  const value2Edit = await page
    .getByTestId("input-list-input-edit_urls-2")
    .inputValue();
  const value3Edit = await page
    .getByTestId("input-list-input-edit_urls-3")
    .inputValue();

  if (
    value0Edit !== "test test test test" ||
    value1Edit !== "test1 test1 test1 test1" ||
    value2Edit !== "test2 test2 test2 test2" ||
    value3Edit !== "test3 test3 test3 test3"
  ) {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("input-list-minus-btn-edit_urls-1").click();
  await page.getByTestId("input-list-minus-btn-edit_urls-1").click();
  await page.getByTestId("input-list-minus-btn-edit_urls-1").click();

  const plusButtonLocatorEdit0 = await page.getByTestId(
    "input-list-plus-btn-edit_urls-0",
  );
  const elementCountEdit0 = await plusButtonLocatorEdit0?.count();

  const plusButtonLocatorEdit2 = await page.getByTestId(
    "input-list-plus-btn-edit_urls-1",
  );
  const elementCountEdit2 = await plusButtonLocatorEdit2?.count();

  if (elementCountEdit0 > 1 || elementCountEdit2 > 0) {
    expect(false).toBeTruthy();
  }

  const minusButtonLocatorEdit1 = await page.getByTestId(
    "input-list-minus-btn-edit_urls-1",
  );

  const elementCountMinusEdit1 = await minusButtonLocatorEdit1?.count();

  const minusButtonLocatorEdit2 = await page.getByTestId(
    "input-list-minus-btn-edit_urls-2",
  );

  const elementCountMinusEdit2 = await minusButtonLocatorEdit2?.count();

  if (elementCountMinusEdit1 > 1 || elementCountMinusEdit2 > 0) {
    expect(false).toBeTruthy();
  }
});
