import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { zoomOut } from "../../utils/zoom-out";

test("IntComponent", { tag: ["@release", "@workspace"] }, async ({ page }) => {
  await awaitBootstrapTest(page);

  await page.waitForSelector('[data-testid="blank-flow"]', {
    timeout: 30000,
  });
  await page.getByTestId("blank-flow").click();
  await page.getByTestId("sidebar-search-input").click();
  await page.getByTestId("sidebar-search-input").fill("openai");

  await page.waitForSelector('[data-testid="openaiOpenAI"]', {
    timeout: 3000,
  });

  await page
    .getByTestId("openaiOpenAI")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.getByTestId("canvas_controls_dropdown").click();

  await page.getByTestId("fit_view").click();
  await zoomOut(page, 2);
  await page.getByTestId("canvas_controls_dropdown").click();

  await page.getByTestId("div-generic-node").click();

  await page.getByTestId("edit-button-modal").last().click();
  await page.getByTestId("showmax_tokens").click();

  await page.getByText("Close").last().click();
  await page.getByTestId("int_int_max_tokens").click();
  await page.getByTestId("int_int_max_tokens").fill("1020304050");

  let value = await page.getByTestId("int_int_max_tokens").inputValue();

  if (value != "1020304050") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("int_int_max_tokens").click();
  await page.getByTestId("int_int_max_tokens").fill("0");

  value = await page.getByTestId("int_int_max_tokens").inputValue();

  if (value != "0") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("title-OpenAI").click();

  await page.getByTestId("canvas_controls_dropdown").click();

  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("canvas_controls_dropdown").click();

  await page.getByTestId("edit-button-modal").last().click();

  value = await page.getByTestId("int_int_edit_max_tokens").inputValue();

  if (value != "0") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("int_int_edit_max_tokens").click();
  await page.getByTestId("int_int_edit_max_tokens").fill("60708090");

  await page.locator('//*[@id="showmodel_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showmodel_kwargs"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showmodel_name"]').click();
  expect(
    await page.locator('//*[@id="showmodel_name"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showopenai_api_base"]').click();
  expect(
    await page.locator('//*[@id="showopenai_api_base"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showtemperature"]').click();
  expect(
    await page.locator('//*[@id="showtemperature"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showmodel_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showmodel_kwargs"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showmodel_name"]').click();
  expect(
    await page.locator('//*[@id="showmodel_name"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showopenai_api_base"]').click();
  expect(
    await page.locator('//*[@id="showopenai_api_base"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showtemperature"]').click();
  expect(
    await page.locator('//*[@id="showtemperature"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showmodel_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showmodel_kwargs"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showmodel_name"]').click();
  expect(
    await page.locator('//*[@id="showmodel_name"]').isChecked(),
  ).toBeFalsy();

  await page.locator('//*[@id="showopenai_api_base"]').click();
  expect(
    await page.locator('//*[@id="showopenai_api_base"]').isChecked(),
  ).toBeTruthy();

  await page.locator('//*[@id="showtemperature"]').click();
  expect(
    await page.locator('//*[@id="showtemperature"]').isChecked(),
  ).toBeFalsy();

  await page.getByText("Close").last().click();

  const plusButtonLocator = page.getByTestId("int-input-max_tokens");
  const elementCount = await plusButtonLocator?.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page.getByTestId("edit-button-modal").last().click();

    const valueEditNode = await page
      .getByTestId("int_int_max_tokens")
      .inputValue();

    if (valueEditNode != "128000") {
      expect(false).toBeTruthy();
    }

    await page.getByText("Close").last().click();
    await page.getByTestId("int_int_max_tokens").click();
    await page.getByTestId("int_int_max_tokens").fill("3");

    let value = await page.getByTestId("int_int_max_tokens").inputValue();

    if (value != "3") {
      expect(false).toBeTruthy();
    }

    await page.getByTestId("int_int_max_tokens").click();
    await page.getByTestId("int_int_max_tokens").fill("-3");
    await page.getByTestId("div-generic-node").click();

    value = await page.getByTestId("int_int_max_tokens").inputValue();

    if (value != "0") {
      expect(false).toBeTruthy();
    }
  }
});
