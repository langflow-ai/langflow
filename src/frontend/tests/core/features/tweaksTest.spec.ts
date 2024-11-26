import { expect, test } from "@playwright/test";

test(
  "curl_api_generation",
  { tag: ["@release", "@workspace", "@api"] },

  async ({ page, context }) => {
    await page.goto("/");
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

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();
    await page.getByText("API", { exact: true }).click();
    await page.getByRole("tab", { name: "cURL" }).click();
    await page.getByTestId("icon-Copy").click();
    const handle = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent = await handle.jsonValue();
    const oldValue = clipboardContent;
    expect(clipboardContent.length).toBeGreaterThan(0);
    await page.getByRole("tab", { name: "Tweaks" }).click();
    await page
      .getByRole("heading", { name: "OpenAi" })
      .locator("div")
      .first()
      .click();

    await page.waitForSelector(
      '[data-testid="popover-anchor-input-openai_api_base-edit"]',
      {
        timeout: 1000,
      },
    );

    await page
      .getByTestId("popover-anchor-input-openai_api_base-edit")
      .first()
      .fill("teste");

    await page.getByRole("tab", { name: "cURL" }).click();
    await page.getByTestId("icon-Copy").click();
    const handle2 = await page.evaluateHandle(() =>
      navigator.clipboard.readText(),
    );
    const clipboardContent2 = await handle2.jsonValue();
    const newValue = clipboardContent2;
    expect(oldValue).not.toBe(newValue);
    expect(clipboardContent2.length).toBeGreaterThan(clipboardContent.length);
  },
);

test("check if tweaks are updating when someothing on the flow changes", async ({
  page,
}) => {
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
  await page.getByTestId("sidebar-search-input").fill("Chroma");

  await page.waitForSelector('[data-testid="vectorstoresChroma DB"]', {
    timeout: 1000,
  });

  await page
    .getByTestId("vectorstoresChroma DB")
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
  await page.getByTestId("popover-anchor-input-collection_name").click();
  await page
    .getByTestId("popover-anchor-input-collection_name")
    .fill("collection_name_test_123123123!@#$&*(&%$@");

  await page.getByTestId("popover-anchor-input-persist_directory").click();
  await page
    .getByTestId("popover-anchor-input-persist_directory")
    .fill("persist_directory_123123123!@#$&*(&%$@");

  const focusElementsOnBoard = async ({ page }) => {
    await page.waitForSelector("text=API", { timeout: 30000 });
    const focusElements = await page.getByText("API", { exact: true }).first();
    await focusElements.click();
  };

  await focusElementsOnBoard({ page });

  await page.getByText("Tweaks").nth(1).click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();

  await page.getByText("Python API", { exact: true }).click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();

  await page.getByText("Python Code", { exact: true }).click();

  await page.getByText("collection_name_test_123123123!@#$&*(&%$@").isVisible();
  await page.getByText("persist_directory_123123123!@#$&*(&%$@").isVisible();
});
