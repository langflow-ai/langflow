import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  closeAdvancedOptions,
  disableInspectPanel,
  enableInspectPanel,
  openAdvancedOptions,
} from "../../utils/open-advanced-options";

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
  await adjustScreenView(page, { numberOfZoomOut: 2 });

  await disableInspectPanel(page);

  await page.getByTestId("div-generic-node").click();

  await openAdvancedOptions(page);
  await page.getByTestId("showmax_tokens").click();

  await closeAdvancedOptions(page);
  await page.getByTestId("int_int_max_tokens").click();
  await page.getByTestId("int_int_max_tokens").fill("100000");

  let value = await page.getByTestId("int_int_max_tokens").inputValue();

  expect(value).toBe("100000");

  await page.getByTestId("int_int_max_tokens").click();
  await page.getByTestId("int_int_max_tokens").fill("0");

  value = await page.getByTestId("int_int_max_tokens").inputValue();

  // max_tokens displays "" (empty) when value is 0 = no limit
  expect(value).toBe("");

  await page.getByTestId("title-OpenAI").click();

  await adjustScreenView(page, { numberOfZoomOut: 3 });

  await openAdvancedOptions(page);

  value = await page.getByTestId("int_int_edit_max_tokens").inputValue();

  // max_tokens displays "" (empty) when value is 0 = no limit
  expect(value).toBe("");

  await page.getByTestId("int_int_edit_max_tokens").click();
  await page.getByTestId("int_int_edit_max_tokens").fill("50000");

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

  await closeAdvancedOptions(page);

  const plusButtonLocator = page.getByTestId("int-input-max_tokens");
  const elementCount = await plusButtonLocator?.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await openAdvancedOptions(page);

    const valueEditNode = await page
      .getByTestId("int_int_max_tokens")
      .inputValue();

    expect(valueEditNode).toBe("50000");

    await closeAdvancedOptions(page);
    await page.getByTestId("int_int_max_tokens").click();
    await page.getByTestId("int_int_max_tokens").fill("3");

    let value = await page.getByTestId("int_int_max_tokens").inputValue();

    expect(value).toBe("3");

    await page.getByTestId("int_int_max_tokens").click();
    await page.getByTestId("int_int_max_tokens").fill("-3");
    await page.getByTestId("div-generic-node").click();

    value = await page.getByTestId("int_int_max_tokens").inputValue();

    // -3 clamps to 0; max_tokens displays "" when value is 0 = no limit
    expect(value).toBe("");
  }

  await enableInspectPanel(page);
});
