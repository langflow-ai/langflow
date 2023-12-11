import { expect, test } from "@playwright/test";

test("FloatComponent", async ({ page }) => {
  await page.routeFromHAR("harFiles/backend_12112023.har", {
    url: "**/api/v1/**",
    update: false,
  });
  await page.route("**/api/v1/flows/", async (route) => {
    const json = {
      id: "e9ac1bdc-429b-475d-ac03-d26f9a2a3210",
    };
    await route.fulfill({ json, status: 201 });
  });
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  await page.locator('//*[@id="new-project-btn"]').click();
  await page.waitForTimeout(2000);

  await page.getByPlaceholder("Search").click();
  await page.getByPlaceholder("Search").fill("llamacpp");

  await page.waitForTimeout(2000);

  await page
    .locator('//*[@id="llmsLlamaCpp"]')
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();

  await page.locator('//*[@id="float-input"]').click();
  await page.locator('//*[@id="float-input"]').fill("3");

  let value = await page.locator('//*[@id="float-input"]').inputValue();

  if (value != "1") {
    expect(false).toBeTruthy();
  }

  await page.locator('//*[@id="float-input"]').click();
  await page.locator('//*[@id="float-input"]').fill("-3");

  value = await page.locator('//*[@id="float-input"]').inputValue();

  if (value != "-1") {
    expect(false).toBeTruthy();
  }

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  await page.locator('//*[@id="showcache"]').click();
  expect(await page.locator('//*[@id="showcache"]').isChecked()).toBeTruthy();

  // showecho
  await page.locator('//*[@id="showecho"]').click();
  expect(await page.locator('//*[@id="showecho"]').isChecked()).toBeTruthy();

  // showf16_kv
  await page.locator('//*[@id="showf16_kv"]').click();
  expect(await page.locator('//*[@id="showf16_kv"]').isChecked()).toBeTruthy();

  // showgrammar_path
  await page.locator('//*[@id="showgrammar_path"]').click();
  expect(
    await page.locator('//*[@id="showgrammar_path"]').isChecked()
  ).toBeTruthy();

  // showlast_n_tokens_size
  await page.locator('//*[@id="showlast_n_tokens_size"]').click();
  expect(
    await page.locator('//*[@id="showlast_n_tokens_size"]').isChecked()
  ).toBeTruthy();

  // showlogits_all
  await page.locator('//*[@id="showlogits_all"]').click();
  expect(
    await page.locator('//*[@id="showlogits_all"]').isChecked()
  ).toBeTruthy();

  // showlogprobs
  await page.locator('//*[@id="showlogprobs"]').click();
  expect(
    await page.locator('//*[@id="showlogprobs"]').isChecked()
  ).toBeTruthy();

  // showlora_base
  await page.locator('//*[@id="showlora_base"]').click();
  expect(
    await page.locator('//*[@id="showlora_base"]').isChecked()
  ).toBeTruthy();

  // showlora_path
  await page.locator('//*[@id="showlora_path"]').click();
  expect(
    await page.locator('//*[@id="showlora_path"]').isChecked()
  ).toBeTruthy();

  // showmax_tokens
  await page.locator('//*[@id="showmax_tokens"]').click();
  expect(
    await page.locator('//*[@id="showmax_tokens"]').isChecked()
  ).toBeTruthy();

  // showmetadata
  await page.locator('//*[@id="showmetadata"]').click();
  expect(
    await page.locator('//*[@id="showmetadata"]').isChecked()
  ).toBeTruthy();

  // showmodel_kwargs
  await page.locator('//*[@id="showmodel_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showmodel_kwargs"]').isChecked()
  ).toBeTruthy();

  // showmodel_path
  await page.locator('//*[@id="showmodel_path"]').click();
  expect(
    await page.locator('//*[@id="showmodel_path"]').isChecked()
  ).toBeFalsy();

  // shown_batch
  await page.locator('//*[@id="shown_batch"]').click();
  expect(await page.locator('//*[@id="shown_batch"]').isChecked()).toBeTruthy();

  // shown_ctx
  await page.locator('//*[@id="shown_ctx"]').click();
  expect(await page.locator('//*[@id="shown_ctx"]').isChecked()).toBeTruthy();

  // shown_gpu_layers
  await page.locator('//*[@id="shown_gpu_layers"]').click();
  expect(
    await page.locator('//*[@id="shown_gpu_layers"]').isChecked()
  ).toBeTruthy();

  // shown_parts
  await page.locator('//*[@id="shown_parts"]').click();
  expect(await page.locator('//*[@id="shown_parts"]').isChecked()).toBeTruthy();

  // shown_threads
  await page.locator('//*[@id="shown_threads"]').click();
  expect(
    await page.locator('//*[@id="shown_threads"]').isChecked()
  ).toBeTruthy();

  // showrepeat_penalty
  await page.locator('//*[@id="showrepeat_penalty"]').click();
  expect(
    await page.locator('//*[@id="showrepeat_penalty"]').isChecked()
  ).toBeTruthy();

  // showrope_freq_base
  await page.locator('//*[@id="showrope_freq_base"]').click();
  expect(
    await page.locator('//*[@id="showrope_freq_base"]').isChecked()
  ).toBeTruthy();

  // showrope_freq_scale
  await page.locator('//*[@id="showrope_freq_scale"]').click();
  expect(
    await page.locator('//*[@id="showrope_freq_scale"]').isChecked()
  ).toBeTruthy();

  // showseed
  await page.locator('//*[@id="showseed"]').click();
  expect(await page.locator('//*[@id="showseed"]').isChecked()).toBeTruthy();

  // showstop
  await page.locator('//*[@id="showstop"]').click();
  expect(await page.locator('//*[@id="showstop"]').isChecked()).toBeTruthy();

  // showstreaming
  await page.locator('//*[@id="showstreaming"]').click();
  expect(
    await page.locator('//*[@id="showstreaming"]').isChecked()
  ).toBeTruthy();

  // showsuffix
  await page.locator('//*[@id="showsuffix"]').click();
  expect(await page.locator('//*[@id="showsuffix"]').isChecked()).toBeTruthy();

  // showtags
  await page.locator('//*[@id="showtags"]').click();
  expect(await page.locator('//*[@id="showtags"]').isChecked()).toBeTruthy();

  // showtemperature
  await page.locator('//*[@id="showtemperature"]').click();
  expect(
    await page.locator('//*[@id="showtemperature"]').isChecked()
  ).toBeFalsy();

  // showtop_k
  await page.locator('//*[@id="showtop_k"]').click();
  expect(await page.locator('//*[@id="showtop_k"]').isChecked()).toBeTruthy();

  // showtop_p
  await page.locator('//*[@id="showtop_p"]').click();
  expect(await page.locator('//*[@id="showtop_p"]').isChecked()).toBeTruthy();

  // showuse_mlock
  await page.locator('//*[@id="showuse_mlock"]').click();
  expect(
    await page.locator('//*[@id="showuse_mlock"]').isChecked()
  ).toBeTruthy();

  // showuse_mmap
  await page.locator('//*[@id="showuse_mmap"]').click();
  expect(
    await page.locator('//*[@id="showuse_mmap"]').isChecked()
  ).toBeTruthy();

  // showverbose
  await page.locator('//*[@id="showverbose"]').click();
  expect(await page.locator('//*[@id="showverbose"]').isChecked()).toBeTruthy();

  // showvocab_only
  await page.locator('//*[@id="showvocab_only"]').click();
  expect(
    await page.locator('//*[@id="showvocab_only"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showcache"]').click();
  expect(await page.locator('//*[@id="showcache"]').isChecked()).toBeFalsy();

  // showecho
  await page.locator('//*[@id="showecho"]').click();
  expect(await page.locator('//*[@id="showecho"]').isChecked()).toBeFalsy();

  // showf16_kv
  await page.locator('//*[@id="showf16_kv"]').click();
  expect(await page.locator('//*[@id="showf16_kv"]').isChecked()).toBeFalsy();

  // showgrammar_path
  await page.locator('//*[@id="showgrammar_path"]').click();
  expect(
    await page.locator('//*[@id="showgrammar_path"]').isChecked()
  ).toBeFalsy();

  // showlast_n_tokens_size
  await page.locator('//*[@id="showlast_n_tokens_size"]').click();
  expect(
    await page.locator('//*[@id="showlast_n_tokens_size"]').isChecked()
  ).toBeFalsy();

  // showlogits_all
  await page.locator('//*[@id="showlogits_all"]').click();
  expect(
    await page.locator('//*[@id="showlogits_all"]').isChecked()
  ).toBeFalsy();

  // showlogprobs
  await page.locator('//*[@id="showlogprobs"]').click();
  expect(await page.locator('//*[@id="showlogprobs"]').isChecked()).toBeFalsy();

  // showlora_base
  await page.locator('//*[@id="showlora_base"]').click();
  expect(
    await page.locator('//*[@id="showlora_base"]').isChecked()
  ).toBeFalsy();

  // showlora_path
  await page.locator('//*[@id="showlora_path"]').click();
  expect(
    await page.locator('//*[@id="showlora_path"]').isChecked()
  ).toBeFalsy();

  // showmax_tokens
  await page.locator('//*[@id="showmax_tokens"]').click();
  expect(
    await page.locator('//*[@id="showmax_tokens"]').isChecked()
  ).toBeFalsy();

  // showmetadata
  await page.locator('//*[@id="showmetadata"]').click();
  expect(await page.locator('//*[@id="showmetadata"]').isChecked()).toBeFalsy();

  // showmodel_kwargs
  await page.locator('//*[@id="showmodel_kwargs"]').click();
  expect(
    await page.locator('//*[@id="showmodel_kwargs"]').isChecked()
  ).toBeFalsy();

  // showmodel_path
  await page.locator('//*[@id="showmodel_path"]').click();
  expect(
    await page.locator('//*[@id="showmodel_path"]').isChecked()
  ).toBeTruthy();

  // shown_batch
  await page.locator('//*[@id="shown_batch"]').click();
  expect(await page.locator('//*[@id="shown_batch"]').isChecked()).toBeFalsy();

  // shown_ctx
  await page.locator('//*[@id="shown_ctx"]').click();
  expect(await page.locator('//*[@id="shown_ctx"]').isChecked()).toBeFalsy();

  // shown_gpu_layers
  await page.locator('//*[@id="shown_gpu_layers"]').click();
  expect(
    await page.locator('//*[@id="shown_gpu_layers"]').isChecked()
  ).toBeFalsy();

  // shown_parts
  await page.locator('//*[@id="shown_parts"]').click();
  expect(await page.locator('//*[@id="shown_parts"]').isChecked()).toBeFalsy();

  // shown_threads
  await page.locator('//*[@id="shown_threads"]').click();
  expect(
    await page.locator('//*[@id="shown_threads"]').isChecked()
  ).toBeFalsy();

  // showrepeat_penalty
  await page.locator('//*[@id="showrepeat_penalty"]').click();
  expect(
    await page.locator('//*[@id="showrepeat_penalty"]').isChecked()
  ).toBeFalsy();

  // showrope_freq_base
  await page.locator('//*[@id="showrope_freq_base"]').click();
  expect(
    await page.locator('//*[@id="showrope_freq_base"]').isChecked()
  ).toBeFalsy();

  // showrope_freq_scale
  await page.locator('//*[@id="showrope_freq_scale"]').click();
  expect(
    await page.locator('//*[@id="showrope_freq_scale"]').isChecked()
  ).toBeFalsy();

  // showseed
  await page.locator('//*[@id="showseed"]').click();
  expect(await page.locator('//*[@id="showseed"]').isChecked()).toBeFalsy();

  // showstop
  await page.locator('//*[@id="showstop"]').click();
  expect(await page.locator('//*[@id="showstop"]').isChecked()).toBeFalsy();

  // showstreaming
  await page.locator('//*[@id="showstreaming"]').click();
  expect(
    await page.locator('//*[@id="showstreaming"]').isChecked()
  ).toBeFalsy();

  // showsuffix
  await page.locator('//*[@id="showsuffix"]').click();
  expect(await page.locator('//*[@id="showsuffix"]').isChecked()).toBeFalsy();

  // showtags
  await page.locator('//*[@id="showtags"]').click();
  expect(await page.locator('//*[@id="showtags"]').isChecked()).toBeFalsy();

  // showtop_k
  await page.locator('//*[@id="showtop_k"]').click();
  expect(await page.locator('//*[@id="showtop_k"]').isChecked()).toBeFalsy();

  // showtop_p
  await page.locator('//*[@id="showtop_p"]').click();
  expect(await page.locator('//*[@id="showtop_p"]').isChecked()).toBeFalsy();

  // showuse_mlock
  await page.locator('//*[@id="showuse_mlock"]').click();
  expect(
    await page.locator('//*[@id="showuse_mlock"]').isChecked()
  ).toBeFalsy();

  // showuse_mmap
  await page.locator('//*[@id="showuse_mmap"]').click();
  expect(await page.locator('//*[@id="showuse_mmap"]').isChecked()).toBeFalsy();

  // showverbose
  await page.locator('//*[@id="showverbose"]').click();
  expect(await page.locator('//*[@id="showverbose"]').isChecked()).toBeFalsy();

  // showvocab_only
  await page.locator('//*[@id="showvocab_only"]').click();
  expect(
    await page.locator('//*[@id="showvocab_only"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="saveChangesBtn"]').click();

  const plusButtonLocator = page.locator('//*[@id="float-input"]');
  const elementCount = await plusButtonLocator.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("edit-button-modal").click();

    // showtemperature
    await page.locator('//*[@id="showtemperature"]').click();
    expect(
      await page.locator('//*[@id="showtemperature"]').isChecked()
    ).toBeTruthy();

    await page.locator('//*[@id="saveChangesBtn"]').click();
    await page.locator('//*[@id="float-input"]').click();
    await page.locator('//*[@id="float-input"]').fill("3");

    let value = await page.locator('//*[@id="float-input"]').inputValue();

    if (value != "1") {
      expect(false).toBeTruthy();
    }

    await page.locator('//*[@id="float-input"]').click();
    await page.locator('//*[@id="float-input"]').fill("-3");

    value = await page.locator('//*[@id="float-input"]').inputValue();

    if (value != "-1") {
      expect(false).toBeTruthy();
    }
  }
});
