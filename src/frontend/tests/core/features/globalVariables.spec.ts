import { expect, test } from "@playwright/test";

test(
  "user must be able to save or delete a global variable",
  { tag: ["@release", "@workspace", "@api"] },
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
    await page.getByTestId("sidebar-search-input").fill("openai");

    await page.waitForSelector('[data-testid="modelsOpenAI"]', {
      timeout: 1000,
    });

    await page
      .getByTestId("modelsOpenAI")
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

    const genericName = Math.random().toString();
    const credentialName = Math.random().toString();

    await page.getByTestId("icon-Globe").nth(0).click();
    await page.getByText("Add New Variable", { exact: true }).click();
    await page
      .getByPlaceholder("Insert a name for the variable...")
      .fill(genericName);
    await page.getByText("Generic", { exact: true }).first().isVisible();
    await page
      .getByPlaceholder("Insert a value for the variable...")
      .fill("This is a test of generic variable value");
    await page.getByText("Save Variable", { exact: true }).click();
    expect(page.getByText(genericName, { exact: true })).not.toBeNull();
    await page.getByText(genericName, { exact: true }).isVisible();

    await page.getByText("Add New Variable", { exact: true }).click();
    await page
      .getByPlaceholder("Insert a name for the variable...")
      .fill(credentialName);
    await page.getByTestId("select-type-global-variables").first().click();
    await page.getByText("Credential", { exact: true }).last().click();
    await page
      .getByPlaceholder("Insert a value for the variable...")
      .fill("This is a test of credential variable value");
    await page.getByText("Save Variable", { exact: true }).click();
    expect(page.getByText(credentialName, { exact: true })).not.toBeNull();
    await page.getByText(credentialName, { exact: true }).isVisible();

    await page
      .getByText(credentialName, { exact: true })
      .hover()
      .then(async () => {
        await page.getByTestId("icon-Trash2").last().click();
        await page.getByText("Delete", { exact: true }).nth(1).click();
      });
  },
);
