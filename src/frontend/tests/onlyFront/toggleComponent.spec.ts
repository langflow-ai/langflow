import { expect, test } from "@playwright/test";

test("ToggleComponent", async ({ page }) => {
  await page.routeFromHAR("harFiles/langflow.har", {
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
  await page.getByPlaceholder("Search").fill("directoryLoader");

  await page.waitForTimeout(2000);
  await page
    .getByTestId("documentloadersDirectoryLoader")
    .dragTo(page.locator('//*[@id="react-flow-id"]'));
  await page.mouse.up();
  await page.mouse.down();
  await page.getByTestId("div-generic-node").click();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  await page.locator('//*[@id="showload_hidden"]').click();
  expect(
    await page.locator('//*[@id="showload_hidden"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="saveChangesBtn"]').click();

  await page.locator('//*[@id="toggle-1"]').click();
  expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="toggle-1"]').click();
  expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="toggle-1"]').click();
  expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="toggle-1"]').click();
  expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="toggle-1"]').click();
  expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeFalsy();

  await page.getByTestId("div-generic-node").click();

  await page.getByTestId("more-options-modal").click();
  await page.getByTestId("edit-button-modal").click();

  expect(
    await page.locator('//*[@id="toggle-edit-1"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showglob"]').click();
  expect(await page.locator('//*[@id="showglob"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showload_hidden"]').click();
  expect(
    await page.locator('//*[@id="showload_hidden"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showmax_concurrency"]').click();
  expect(
    await page.locator('//*[@id="showmax_concurrency"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showmetadata"]').click();
  expect(await page.locator('//*[@id="showmetadata"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showpath"]').click();
  expect(await page.locator('//*[@id="showpath"]').isChecked()).toBeFalsy();

  await page.locator('//*[@id="showrecursive"]').click();
  expect(
    await page.locator('//*[@id="showrecursive"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showsilent_errors"]').click();
  expect(
    await page.locator('//*[@id="showsilent_errors"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showuse_multithreading"]').click();
  expect(
    await page.locator('//*[@id="showuse_multithreading"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showglob"]').click();
  expect(await page.locator('//*[@id="showglob"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showmax_concurrency"]').click();
  expect(
    await page.locator('//*[@id="showmax_concurrency"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showmetadata"]').click();
  expect(
    await page.locator('//*[@id="showmetadata"]').isChecked()
  ).toBeTruthy();

  await page.locator('//*[@id="showpath"]').click();
  expect(await page.locator('//*[@id="showpath"]').isChecked()).toBeTruthy();

  await page.locator('//*[@id="showrecursive"]').click();
  expect(
    await page.locator('//*[@id="showrecursive"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showsilent_errors"]').click();
  expect(
    await page.locator('//*[@id="showsilent_errors"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="showuse_multithreading"]').click();
  expect(
    await page.locator('//*[@id="showuse_multithreading"]').isChecked()
  ).toBeFalsy();

  await page.locator('//*[@id="saveChangesBtn"]').click();

  const plusButtonLocator = page.locator('//*[@id="toggle-1"]');
  const elementCount = await plusButtonLocator.count();
  if (elementCount === 0) {
    expect(true).toBeTruthy();

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("edit-button-modal").click();

    await page.locator('//*[@id="showload_hidden"]').click();
    expect(
      await page.locator('//*[@id="showload_hidden"]').isChecked()
    ).toBeTruthy();

    expect(
      await page.locator('//*[@id="toggle-edit-1"]').isChecked()
    ).toBeFalsy();

    await page.locator('//*[@id="saveChangesBtn"]').click();

    await page.locator('//*[@id="toggle-1"]').click();
    expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeTruthy();

    await page.locator('//*[@id="toggle-1"]').click();
    expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeFalsy();

    await page.locator('//*[@id="toggle-1"]').click();
    expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeTruthy();

    await page.locator('//*[@id="toggle-1"]').click();
    expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeFalsy();

    await page.locator('//*[@id="toggle-1"]').click();
    expect(await page.locator('//*[@id="toggle-1"]').isChecked()).toBeTruthy();
  }
});
