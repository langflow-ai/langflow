import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { TEXTS } from "../../utils/constants/texts";

import { openBlankFlow } from "../../utils/flow/open-blank-flow";
import {
  addParameterToNode,
  closeParametersPanel,
  openParametersPanel,
  toggleParameterOnNode,
} from "../../utils/open-advanced-options";
import { skipIfComponentUnavailable } from "../../utils/skip-if-component-unavailable";

test("IntComponent", { tag: ["@release", "@workspace"] }, async ({ page }) => {
  await openBlankFlow(page);
  await page.getByTestId("sidebar-search-input").click();
  await page
    .getByTestId("sidebar-search-input")
    .fill(TEXTS.providerOpenAiSearch);

  await skipIfComponentUnavailable(page.getByTestId("openaiOpenAI"), "OpenAI");

  await page
    .getByTestId("openaiOpenAI")
    .first()
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await adjustScreenView(page, { numberOfZoomOut: 2 });

  await page.getByTestId("div-generic-node").click();

  // LE-1810: the parameters panel adds hidden fields to the node; values are
  // edited on the node itself.
  await addParameterToNode(page, "max_tokens");
  await closeParametersPanel(page);

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

  // max_tokens is on the node — the value stays editable there
  value = await page.getByTestId("int_int_max_tokens").inputValue();

  // max_tokens displays "" (empty) when value is 0 = no limit
  expect(value).toBe("");

  await page.getByTestId("int_int_max_tokens").click();
  await page.getByTestId("int_int_max_tokens").fill("50000");

  // LE-1810: visibility rounds now happen through the panel Add/Remove
  // actions — the row swaps between the two buttons.
  await openParametersPanel(page);

  await toggleParameterOnNode(page, "model_kwargs");
  await expect(page.getByTestId("inspector-remove-model_kwargs")).toBeVisible();

  await toggleParameterOnNode(page, "model_name");
  await expect(page.getByTestId("inspector-add-model_name")).toBeVisible();

  await toggleParameterOnNode(page, "openai_api_base");
  await expect(
    page.getByTestId("inspector-remove-openai_api_base"),
  ).toBeVisible();

  await toggleParameterOnNode(page, "temperature");
  await expect(page.getByTestId("inspector-add-temperature")).toBeVisible();

  await toggleParameterOnNode(page, "model_kwargs");
  await expect(page.getByTestId("inspector-add-model_kwargs")).toBeVisible();

  await toggleParameterOnNode(page, "model_name");
  await expect(page.getByTestId("inspector-remove-model_name")).toBeVisible();

  await toggleParameterOnNode(page, "openai_api_base");
  await expect(page.getByTestId("inspector-add-openai_api_base")).toBeVisible();

  await toggleParameterOnNode(page, "temperature");
  await expect(page.getByTestId("inspector-remove-temperature")).toBeVisible();

  await toggleParameterOnNode(page, "model_kwargs");
  await expect(page.getByTestId("inspector-remove-model_kwargs")).toBeVisible();

  await toggleParameterOnNode(page, "model_name");
  await expect(page.getByTestId("inspector-add-model_name")).toBeVisible();

  await toggleParameterOnNode(page, "openai_api_base");
  await expect(
    page.getByTestId("inspector-remove-openai_api_base"),
  ).toBeVisible();

  await toggleParameterOnNode(page, "temperature");
  await expect(page.getByTestId("inspector-add-temperature")).toBeVisible();

  await closeParametersPanel(page);

  const plusButtonLocator = page.getByTestId("int-input-max_tokens");
  const elementCount = await plusButtonLocator?.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    const valueOnNode = await page
      .getByTestId("int_int_max_tokens")
      .inputValue();

    expect(valueOnNode).toBe("50000");

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
});
