import { expect, test } from "@playwright/test";

test(
  "ToggleComponent",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector('[data-testid="mainpage_title"]', {
      timeout: 30000,
    });

    await page.waitForSelector('[id="new-project-btn"]', {
      timeout: 30000,
    });

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
      await page.getByText("New Flow", { exact: true }).click();
      await page.waitForSelector('[data-testid="modal-title"]', {
        timeout: 3000,
      });
      modalCount = await page.getByTestId("modal-title")?.count();
    }
    await page.waitForSelector('[data-testid="blank-flow"]', {
      timeout: 30000,
    });
    await page.getByTestId("blank-flow").click();

    await page.getByTestId("sidebar-search-input").click();
    await page.getByTestId("sidebar-search-input").fill("directory");

    await page.waitForSelector('[data-testid="dataDirectory"]', {
      timeout: 30000,
    });
    await page
      .getByTestId("dataDirectory")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("div-generic-node").click();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();

    await page.locator('//*[@id="showload_hidden"]').click();
    expect(
      await page.locator('//*[@id="showload_hidden"]').isChecked(),
    ).toBeTruthy();

    await page.getByText("Close").last().click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeTruthy();

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeFalsy();

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeTruthy();

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeFalsy();

    await page.getByTestId("toggle_bool_load_hidden").click();
    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeTruthy();

    await page.getByTestId("div-generic-node").click();

    await page.waitForSelector('[data-testid="fit_view"]', {
      timeout: 100000,
    });

    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();

    expect(
      await page.getByTestId("toggle_bool_load_hidden").isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showload_hidden"]').click();
    expect(
      await page.locator('//*[@id="showload_hidden"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showmax_concurrency"]').click();
    expect(
      await page.locator('//*[@id="showmax_concurrency"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showpath"]').click();
    expect(await page.locator('//*[@id="showpath"]').isChecked()).toBeFalsy();

    await page.locator('//*[@id="showrecursive"]').click();
    expect(
      await page.locator('//*[@id="showrecursive"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showsilent_errors"]').click();
    expect(
      await page.locator('//*[@id="showsilent_errors"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showuse_multithreading"]').click();
    expect(
      await page.locator('//*[@id="showuse_multithreading"]').isChecked(),
    ).toBeTruthy();

    await page.locator('//*[@id="showmax_concurrency"]').click();
    expect(
      await page.locator('//*[@id="showmax_concurrency"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showpath"]').click();
    expect(await page.locator('//*[@id="showpath"]').isChecked()).toBeTruthy();

    await page.locator('//*[@id="showrecursive"]').click();
    expect(
      await page.locator('//*[@id="showrecursive"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showsilent_errors"]').click();
    expect(
      await page.locator('//*[@id="showsilent_errors"]').isChecked(),
    ).toBeFalsy();

    await page.locator('//*[@id="showuse_multithreading"]').click();
    expect(
      await page.locator('//*[@id="showuse_multithreading"]').isChecked(),
    ).toBeFalsy();

    await page.getByText("Close").last().click();

    const plusButtonLocator = page.getByTestId("toggle_bool_load_hidden");
    const elementCount = await plusButtonLocator?.count();
    if (elementCount === 0) {
      expect(true).toBeTruthy();

      await page.getByTestId("div-generic-node").click();

      await page.getByTestId("more-options-modal").click();
      await page.getByTestId("advanced-button-modal").click();

      await page.locator('//*[@id="showload_hidden"]').click();
      expect(
        await page.locator('//*[@id="showload_hidden"]').isChecked(),
      ).toBeTruthy();

      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeTruthy();

      await page.getByText("Close").last().click();

      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeFalsy();

      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeTruthy();

      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeFalsy();

      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeTruthy();

      await page.getByTestId("toggle_bool_load_hidden").click();
      expect(
        await page.getByTestId("toggle_bool_load_hidden").isChecked(),
      ).toBeFalsy();
    }
  },
);
