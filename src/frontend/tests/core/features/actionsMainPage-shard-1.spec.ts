import { expect, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { TID } from "../../utils/constants/testIds";
import { TEXTS } from "../../utils/constants/texts";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";

test(
  "select and delete a flow",
  { tag: ["@release", "@mainpage"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    await page.getByTestId("side_nav_options_all-templates").click();
    await page
      .getByRole("heading", { name: TEXTS.templateBasicPrompting })
      .click();

    await page.waitForSelector('[data-testid="sidebar-search-input"]', {
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
    await page.getByText(TEXTS.delete).last().click();
    await page.getByText("This can't be undone.").isVisible({
      timeout: 1000,
    });

    //confirm the deletion in the modal
    await page.getByText(TEXTS.delete).last().click();

    await expect(
      page.getByText("Selected items deleted successfully"),
    ).toBeVisible();
  },
);

test("search flows", { tag: ["@release", "@mainpage"] }, async ({ page }) => {
  await awaitBootstrapTest(page);

  await page.getByTestId("side_nav_options_all-templates").click();
  await page
    .getByRole("heading", { name: TEXTS.templateBasicPrompting })
    .click();

  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();

  await expect(page.getByTestId(TID.newProjectBtn)).toBeVisible();
  await openTemplatesModal(page);
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Memory Chatbot" }).click();

  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();
  await openTemplatesModal(page);
  await page.getByTestId("side_nav_options_all-templates").click();
  await page.getByRole("heading", { name: "Document Q&A" }).click();

  await page.waitForSelector('[data-testid="sidebar-search-input"]', {
    timeout: 100000,
  });

  await page.getByTestId("icon-ChevronLeft").first().click();
  await page.getByPlaceholder("Search flows").fill("Memory Chatbot");
  await expect(page.getByText("Memory Chatbot", { exact: true })).toBeVisible();
  await page.getByText("Document Q&A", { exact: true }).isHidden();
  await page
    .getByText(TEXTS.templateBasicPrompting, { exact: true })
    .isHidden();
});

test(
  "search components",
  { tag: ["@release", "@mainpage"] },
  async ({ page }) => {
    await awaitBootstrapTest(page);

    if (await page.getByTestId("components-btn").isVisible()) {
      await page.getByTestId("side_nav_options_all-templates").click();
      await page
        .getByRole("heading", { name: TEXTS.templateBasicPrompting })
        .click();

      await adjustScreenView(page, { numberOfZoomOut: 2 });

      await page.getByText(TEXTS.componentChatInput).first().click();
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

      await page.waitForSelector('[data-testid="sidebar-search-input"]', {
        timeout: 100000,
      });

      await page.getByTestId("icon-ChevronLeft").first().click();

      const exitButton = await page
        .getByText(TEXTS.exit, { exact: true })
        .count();

      if (exitButton > 0) {
        await page.getByText(TEXTS.exit, { exact: true }).click();
      }

      await page.getByTestId("components-btn").click();
      await page.getByPlaceholder("Search components").fill("Chat Input");
      await expect(
        page.getByText(TEXTS.componentChatInput, { exact: true }),
      ).toBeVisible();
      await page.getByText("Prompt", { exact: true }).isHidden();
      await page.getByText("OpenAI", { exact: true }).isHidden();
    }
  },
);
