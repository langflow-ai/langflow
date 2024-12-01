import { expect, test } from "@playwright/test";

test(
  "FloatComponent",
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
    await page.getByTestId("sidebar-search-input").fill("ollama");

    await page.waitForSelector('[data-testid="modelsOllama"]', {
      timeout: 30000,
    });

    await page
      .getByTestId("modelsOllama")
      .dragTo(page.locator('//*[@id="react-flow-id"]'));
    await page.mouse.up();
    await page.mouse.down();
    await page.getByTestId("fit_view").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();
    await page.getByTestId("zoom_out").click();

    await page.locator('//*[@id="float_float_temperature"]').click();
    await page.locator('//*[@id="float_float_temperature"]').fill("");
    await page.locator('//*[@id="float_float_temperature"]').fill("3");

    let value = await page
      .locator('//*[@id="float_float_temperature"]')
      .inputValue();

    expect(value).toBe("2");

    await page.locator('//*[@id="float_float_temperature"]').click();
    await page.locator('//*[@id="float_float_temperature"]').fill("");
    await page.locator('//*[@id="float_float_temperature"]').fill("-3");

    value = await page
      .locator('//*[@id="float_float_temperature"]')
      .inputValue();

    expect(value).toBe("-2");

    await page.getByTestId("more-options-modal").click();
    await page.getByTestId("advanced-button-modal").click();

    await page.getByTestId("showmirostat_eta").click();
    expect(
      await page.locator('//*[@id="showmirostat_eta"]').isChecked(),
    ).toBeTruthy();

    await page.getByTestId("showmirostat_eta").click();
    expect(
      await page.locator('//*[@id="showmirostat_eta"]').isChecked(),
    ).toBeFalsy();

    await page.getByTestId("showmirostat_eta").click();
    expect(
      await page.locator('//*[@id="showmirostat_eta"]').isChecked(),
    ).toBeTruthy();

    await page.getByTestId("showmirostat_eta").click();
    expect(
      await page.locator('//*[@id="showmirostat_eta"]').isChecked(),
    ).toBeFalsy();

    await page.getByTestId("showmirostat_tau").click();
    expect(
      await page.locator('//*[@id="showmirostat_tau"]').isChecked(),
    ).toBeTruthy();

    await page.getByTestId("showmirostat_tau").click();
    expect(
      await page.locator('//*[@id="showmirostat_tau"]').isChecked(),
    ).toBeFalsy();

    await page.getByText("Close").last().click();

    const plusButtonLocator = page.locator(
      '//*[@id="float_float_temperature"]',
    );
    const elementCount = await plusButtonLocator?.count();
    if (elementCount === 0) {
      expect(true).toBeTruthy();

      await page.getByTestId("more-options-modal").click();
      await page.getByTestId("advanced-button-modal").click();

      // showtemperature
      await page.locator('//*[@id="showtemperature"]').click();
      expect(
        await page.locator('//*[@id="showtemperature"]').isChecked(),
      ).toBeTruthy();

      await page.getByText("Close").last().click();
      await page.locator('//*[@id="float_float_temperature"]').click();
      await page.getByTestId("float_float_temperature").fill("");

      await page.locator('//*[@id="float_float_temperature"]').fill("3");

      let value = await page
        .locator('//*[@id="float_float_temperature"]')
        .inputValue();

      expect(value).toBe("1");

      await page.locator('//*[@id="float_float_temperature"]').click();
      await page.getByTestId("float_float_temperature").fill("");

      await page.locator('//*[@id="float_float_temperature"]').fill("-3");

      value = await page
        .locator('//*[@id="float_float_temperature"]')
        .inputValue();

      expect(value).toBe("-1");
    }
  },
);
