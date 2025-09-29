import test, { expect } from "playwright/test";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { cleanOldFolders } from "../../utils/clean-old-folders";
import { convertTestName } from "../../utils/convert-test-name";
import { navigateSettingsPages } from "../../utils/go-to-settings";

test(
  "user must be able to see starter projects for mcp servers",
  { tag: ["@release", "@workspace", "@components"] },
  async ({ page }) => {
    //starter mcp project

    await awaitBootstrapTest(page, {
      skipModal: true,
    });

    await cleanOldFolders(page);

    await navigateSettingsPages(page, "Settings", "MCP Servers");

    expect(await page.getByTestId("mcp_server_name_0").textContent()).toContain(
      "lf-starter_project",
    );

    await page.getByTestId("icon-ChevronLeft").first().click();

    //add new folders

    await page.getByTestId("add-project-button").click();
    await page.getByTestId("add-project-button").click();

    await navigateSettingsPages(page, "Settings", "MCP Servers");

    expect(await page.getByTestId("mcp_server_name_0").textContent()).toContain(
      "lf-starter_project",
    );

    expect(
      await page.getByText("lf-new_project", { exact: true }).count(),
    ).toBe(1);
    expect(
      await page.getByText("lf-new_project_1", { exact: true }).count(),
    ).toBe(1);

    await page.getByTestId("icon-ChevronLeft").first().click();

    //rename a folder

    const getFirstFolderName = convertTestName(
      (await page.getByText("New Project").first().textContent()) as string,
    );

    await page
      .getByText("New Project")
      .first()
      .hover()
      .then(async () => {
        await page
          .getByTestId(`more-options-button_${getFirstFolderName}`)
          .last()
          .click();
        await page.getByText("Rename", { exact: true }).last().click();
        await page.getByTestId("input-project").last().fill("renamed_project");
      });

    await navigateSettingsPages(page, "Settings", "MCP Servers");

    expect(await page.getByTestId("mcp_server_name_0").textContent()).toContain(
      "lf-starter_project",
    );

    expect(
      await page.getByText("lf-renamed_project", { exact: true }).count(),
    ).toBe(1);

    //delete a folder

    await page.getByTestId("icon-ChevronLeft").first().click();
    await page
      .getByTestId("sidebar-nav-renamed_project")
      .hover()
      .then(async () => {
        await page
          .getByTestId("more-options-button_renamed_project")
          .last()
          .click();
        await page.getByText("Delete", { exact: true }).last().click();
        await page.getByText("Delete", { exact: true }).last().click();
      });

    await navigateSettingsPages(page, "Settings", "MCP Servers");

    expect(await page.getByTestId("mcp_server_name_0").textContent()).toContain(
      "lf-starter_project",
    );
    expect(
      await page.getByText("lf-renamed_project", { exact: true }).count(),
    ).toBe(0);
  },
);
