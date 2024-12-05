import { test } from "@playwright/test";

test(
  "select and delete a flow",
  { tag: ["@release", "@api"] },
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
    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 5000,
    });

    await page.getByTestId("home-dropdown-menu").first().click();
    await page.waitForSelector('[data-testid="icon-Trash2"]', {
      timeout: 1000,
    });
    // click on the delete button
    await page.getByText("Delete").last().click();
    await page.getByText("Note: This action is irreversible.").isVisible({
      timeout: 1000,
    });

    //confirm the deletion in the modal
    await page.getByText("Delete").last().click();

    await page.getByText("Selected items deleted successfully").isVisible();
  },
);

test("search flows", { tag: ["@release"] }, async ({ page }) => {
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
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await page.getByText("New Flow").isVisible();
  await page.getByText("New Flow", { exact: true }).click();
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Memory Chatbot" }).click();

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();
  await page.getByText("New Flow", { exact: true }).click();
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Document Q&A" }).click();

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();
  await page.getByPlaceholder("Search flows").fill("Memory Chatbot");
  await page.getByText("Memory Chatbot", { exact: true }).isVisible();
  await page.getByText("Document Q&A", { exact: true }).isHidden();
  await page.getByText("Basic Prompting", { exact: true }).isHidden();
});

test("search components", { tag: ["@release"] }, async ({ page }) => {
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
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Basic Prompting" }).click();

  await page.waitForSelector('[data-testid="fit_view"]', {
    timeout: 100000,
  });

  await page.getByTestId("fit_view").click();
  await page.getByTestId("zoom_out").click();
  await page.getByTestId("zoom_out").click();

  await page.getByText("Chat Input").first().click();
  await page.waitForSelector('[data-testid="more-options-modal"]', {
    timeout: 1000,
  });
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.keyboard.press("Escape");
  await page
    .getByText("Prompt", {
      exact: true,
    })
    .first()
    .click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.keyboard.press("Escape");

  await page
    .getByText("OpenAI", {
      exact: true,
    })
    .first()
    .click();
  await page.getByTestId("more-options-modal").click();

  await page.getByTestId("icon-SaveAll").first().click();
  await page.keyboard.press("Escape");

  await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  const exitButton = await page.getByText("Exit", { exact: true }).count();

  if (exitButton > 0) {
    await page.getByText("Exit", { exact: true }).click();
  }

  await page.getByTestId("components-btn").click();

  await page.getByPlaceholder("Search components").fill("Chat Input");
  await page.getByText("Chat Input", { exact: true }).isVisible();
  await page.getByText("Prompt", { exact: true }).isHidden();
  await page.getByText("OpenAI", { exact: true }).isHidden();
});
