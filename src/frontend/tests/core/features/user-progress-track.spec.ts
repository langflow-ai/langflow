import { BrowserContext, Page } from "playwright/test";
import { DISCORD_URL, GITHUB_URL } from "../../../src/constants/constants";
import { expect, test } from "../../fixtures";
import { addNewUserAndLogin } from "../../utils/add-new-user-and-loggin";
import { cleanAllFlows } from "../../utils/clean-all-flows";
import { cleanOldFolders } from "../../utils/clean-old-folders";
import { TEXTS } from "../../utils/constants/texts";
import { openTemplatesModal } from "../../utils/flow/new-project-flow";
import { selectStarterTemplate } from "../../utils/flow/select-starter-template";
import { waitForFlowEditorReady } from "../../utils/flow/wait-for-flow-editor-ready";

test(
  "admin user must be able to track their progress in getting started",
  { tag: ["@release", "@api"] },
  async ({ page, context }) => {
    await page.goto("/");
    await progressTrackTestFn(page, context);
  },
);

test(
  "normal user must be able to track their progress in getting started",
  { tag: ["@release", "@api"] },
  async ({ page, context }) => {
    await addNewUserAndLogin(page);
    await progressTrackTestFn(page, context, true);
  },
);

async function progressTrackTestFn(
  page: Page,
  context: BrowserContext,
  isNormalUser: boolean = false,
) {
  // Wait for any loading text to disappear
  await page.waitForSelector('text="Loading"', {
    state: "hidden",
    timeout: 30000,
  });

  await cleanAllFlows(page);
  await cleanOldFolders(page);

  await expect(page.getByTestId("new_project_btn_empty_page")).toBeVisible();
  await expect(page.getByTestId("mainpage_title").last()).toBeVisible();
  await expect(page.getByTestId("empty_page_description")).toBeVisible();
  await expect(page.getByTestId("empty_page_github_button")).toBeVisible();
  await expect(page.getByTestId("empty_page_discord_button")).toBeVisible();
  await expect(page.getByTestId("empty_page_drag_and_drop_text")).toBeVisible();
  await expect(
    page.getByTestId("get_started_progress_title"),
  ).not.toBeVisible();

  if (isNormalUser) {
    const [newPageGithub] = await Promise.all([
      context.waitForEvent("page"),
      page.getByTestId("empty_page_github_button").click(),
    ]);
    await newPageGithub.waitForLoadState("domcontentloaded");
    expect(newPageGithub.url()).toContain(GITHUB_URL);

    await newPageGithub.close();
  } else {
    const [newPageDiscord] = await Promise.all([
      context.waitForEvent("page"),
      page.getByTestId("empty_page_discord_button").click(),
    ]);
    await newPageDiscord.waitForLoadState("domcontentloaded");
    expect(newPageDiscord.url()).toContain(DISCORD_URL);

    await newPageDiscord.close();
  }

  await expect(page.getByTestId("mainpage_title")).toBeVisible();
  await expect(page.getByTestId("empty_page_description")).toBeVisible();

  await openTemplatesModal(page, { fromEmptyPage: true });
  await selectStarterTemplate(page, TEXTS.templateBasicPrompting);
  await waitForFlowEditorReady(page);

  await page.getByTestId("icon-ChevronLeft").first().click();

  await expect(page.getByTestId("home-dropdown-menu")).toHaveCount(1);

  await expect(
    page.getByTestId("get_started_progress_percentage").first(),
  ).toHaveText("66%");

  await cleanAllFlows(page);

  await expect(page.getByTestId("home-dropdown-menu")).toHaveCount(0);
  await expect(
    page.getByTestId("get_started_progress_title"),
  ).not.toBeVisible();
  await expect(
    page.getByTestId("github_starred_icon_get_started"),
  ).not.toBeVisible();
  await expect(
    page.getByTestId("create_flow_icon_get_started"),
  ).not.toBeVisible();
  await expect(
    page.getByTestId("discord_joined_icon_get_started"),
  ).not.toBeVisible();
}
