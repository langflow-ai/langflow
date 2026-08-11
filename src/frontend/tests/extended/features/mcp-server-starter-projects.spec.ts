import { expect, test } from "@playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { cleanOldFolders } from "../../utils/clean-old-folders";
import { TEXTS } from "../../utils/constants/texts";
import { navigateSettingsPages } from "../../utils/go-to-settings";
import {
  getSidebarProjectButton,
  getSidebarProjectOptionsButton,
} from "../../utils/project-sidebar";

test(
  "user must be able to see starter projects for mcp servers",
  {
    tag: ["@release", "@workspace", "@components"],
  },
  async ({ page }) => {
    //starter mcp project

    await awaitBootstrapTest(page, {
      skipModal: true,
    });

    await cleanOldFolders(page);

    await navigateSettingsPages(page, "Settings", "MCP Servers");

    await expect(
      page.getByText("lf-starter_project", { exact: true }),
    ).toBeVisible();

    await page.getByTestId("icon-ChevronLeft").first().click();

    //add new folders

    await page.getByTestId("add-project-button").click();
    await page.getByTestId("add-project-button").click();

    await navigateSettingsPages(page, "Settings", "MCP Servers");

    await expect(
      page.getByText("lf-starter_project", { exact: true }),
    ).toBeVisible();

    expect(
      await page.getByText("lf-new_project", { exact: true }).count(),
    ).toBe(1);
    expect(
      await page.getByText("lf-new_project_1", { exact: true }).count(),
    ).toBe(1);

    await page.getByTestId("icon-ChevronLeft").first().click();

    //rename a folder

    const getFirstFolderName = (await page
      .getByText(TEXTS.labelNewProject)
      .first()
      .textContent()) as string;

    await page
      .getByText(TEXTS.labelNewProject)
      .first()
      .hover()
      .then(async () => {
        await getSidebarProjectOptionsButton(page, getFirstFolderName)
          .last()
          .click();
        await page.getByText("Rename", { exact: true }).last().click();
        await page.getByTestId("input-project").last().fill("renamed_project");
        await page.keyboard.press("Enter");
        await page.waitForTimeout(1000);
      });

    await navigateSettingsPages(page, "Settings", "MCP Servers");

    await expect(
      page.getByText("lf-starter_project", { exact: true }),
    ).toBeVisible();

    expect(
      await page.getByText("lf-renamed_project", { exact: true }).count(),
    ).toBe(1);

    //delete a folder

    await page.getByTestId("icon-ChevronLeft").first().click();
    await getSidebarProjectButton(page, "renamed_project")
      .hover()
      .then(async () => {
        await getSidebarProjectOptionsButton(page, "renamed_project")
          .last()
          .click();
        await page.getByText(TEXTS.delete, { exact: true }).last().click();
        await page.getByText(TEXTS.delete, { exact: true }).last().click();
        await page.waitForTimeout(1000);
      });

    await navigateSettingsPages(page, "Settings", "MCP Servers");

    await expect(
      page.getByText("lf-starter_project", { exact: true }),
    ).toBeVisible();
    expect(
      await page.getByText("lf-renamed_project", { exact: true }).count(),
    ).toBe(0);
  },
);

test(
  "user must not be able to add duplicate mcp servers from starter projects",
  {
    tag: ["@release", "@workspace", "@components"],
  },
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

    await page.getByTestId("mcp-btn").click();
    await page.getByText("JSON").last().click();
    await page.getByTestId("icon-copy").click();

    await navigateSettingsPages(page, "Settings", "MCP Servers");

    await page.getByTestId("add-mcp-server-button-page").click();
    await page.getByTestId("json-input").click();
    await page.keyboard.press(`ControlOrMeta+V`);
    await page.getByTestId("add-mcp-server-button").click();

    // Wait for error message to appear
    await expect(page.getByText("Server already exists.")).toBeVisible({
      timeout: 10000,
    });

    const numberOfErrors = await page
      .getByText("Server already exists.")
      .count();
    expect(numberOfErrors).toBe(1);
  },
);
