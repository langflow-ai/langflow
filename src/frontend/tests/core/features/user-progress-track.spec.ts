import { DISCORD_URL, GITHUB_URL } from "../../../src/constants/constants";
import { expect, test } from "../../fixtures";
import { addNewUserAndLogin } from "../../utils/add-new-user-and-loggin";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "admin user must be able to track their progress in getting started",
  { tag: ["@release", "@api"] },
  async ({ page, context }) => {
    await page.goto("/");

    // Wait for any loading text to disappear
    await page.waitForSelector('text="Loading"', {
      state: "hidden",
      timeout: 30000,
    });

    await page.waitForTimeout(2000);

    let emptyButton = page.getByTestId("new_project_btn_empty_page");
    while ((await emptyButton.count()) === 0) {
      await page.getByTestId("home-dropdown-menu").first().click();
      await page.getByTestId("btn_delete_dropdown_menu").first().click();
      await page
        .getByTestId("btn_delete_delete_confirmation_modal")
        .first()
        .click();
      await page.waitForTimeout(1000);
      emptyButton = page.getByTestId("new_project_btn_empty_page");
    }

    await expect(emptyButton).toBeVisible();
    await expect(page.getByTestId("mainpage_title")).toBeVisible();
    await expect(page.getByTestId("empty_page_description")).toBeVisible();
    await expect(page.getByTestId("empty_page_github_button")).toBeVisible();
    await expect(page.getByTestId("empty_page_discord_button")).toBeVisible();
    await expect(
      page.getByTestId("empty_page_drag_and_drop_text"),
    ).toBeVisible();
    await expect(
      page.getByTestId("get_started_progress_title"),
    ).not.toBeVisible();

    await page.getByTestId("empty_page_github_button").click();

    const pagePromiseGithub = context.waitForEvent("page");

    const newPageGithub = await pagePromiseGithub;
    await newPageGithub.waitForTimeout(3000);
    const newUrlGithub = newPageGithub.url();

    await expect(newUrlGithub).toContain(GITHUB_URL);

    await newPageGithub.close();

    await expect(page.getByTestId("mainpage_title")).toBeVisible();
    await expect(page.getByTestId("empty_page_description")).toBeVisible();

    await page.getByTestId("new_project_btn_empty_page").click();

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 100000,
    });

    await expect(page.getByTestId("get_started_progress_title")).toBeVisible();
    await expect(
      page.getByTestId("github_starred_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("create_flow_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("discord_joined_icon_get_started"),
    ).not.toBeVisible();
    await expect(
      page.getByTestId("get_started_progress_percentage").first(),
    ).toHaveText("66%");

    await page.getByTestId("discord_joined_btn_get_started").click();
    const pagePromiseDiscord = context.waitForEvent("page");

    const newPageDiscord = await pagePromiseDiscord;
    await newPageDiscord.waitForTimeout(3000);
    const newUrlDiscord = newPageDiscord.url();

    await expect(newUrlDiscord).toContain(DISCORD_URL);

    await newPageDiscord.close();

    await expect(page.getByTestId("get_started_progress_title")).toBeVisible();
    await expect(
      page.getByTestId("discord_joined_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("create_flow_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("github_starred_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("get_started_progress_percentage").first(),
    ).toHaveText("100%");

    await page.getByTestId("close_get_started_dialog").click();

    await expect(
      page.getByTestId("discord_joined_icon_get_started"),
    ).not.toBeVisible();
    await expect(
      page.getByTestId("create_flow_icon_get_started"),
    ).not.toBeVisible();
    await expect(
      page.getByTestId("github_starred_icon_get_started"),
    ).not.toBeVisible();
  },
);

test(
  "normal user must be able to track their progress in getting started",
  { tag: ["@release", "@api"] },
  async ({ page, context }) => {
    await addNewUserAndLogin(page);

    // Wait for any loading text to disappear
    await page.waitForSelector('text="Loading"', {
      state: "hidden",
      timeout: 30000,
    });

    await page.waitForTimeout(2000);

    let emptyButton = page.getByTestId("new_project_btn_empty_page");
    while ((await emptyButton.count()) === 0) {
      await page.getByTestId("home-dropdown-menu").first().click();
      await page.getByTestId("btn_delete_dropdown_menu").first().click();
      await page
        .getByTestId("btn_delete_delete_confirmation_modal")
        .first()
        .click();
      await page.waitForTimeout(1000);
      emptyButton = page.getByTestId("new_project_btn_empty_page");
    }

    await expect(emptyButton).toBeVisible();
    await expect(page.getByTestId("mainpage_title")).toBeVisible();
    await expect(page.getByTestId("empty_page_description")).toBeVisible();
    await expect(page.getByTestId("empty_page_github_button")).toBeVisible();
    await expect(page.getByTestId("empty_page_discord_button")).toBeVisible();
    await expect(
      page.getByTestId("empty_page_drag_and_drop_text"),
    ).toBeVisible();
    await expect(
      page.getByTestId("get_started_progress_title"),
    ).not.toBeVisible();

    await page.getByTestId("empty_page_github_button").click();

    const pagePromiseGithub = context.waitForEvent("page");

    const newPageGithub = await pagePromiseGithub;
    await newPageGithub.waitForTimeout(3000);
    const newUrlGithub = newPageGithub.url();

    await expect(newUrlGithub).toContain(GITHUB_URL);

    await newPageGithub.close();

    await expect(page.getByTestId("mainpage_title")).toBeVisible();
    await expect(page.getByTestId("empty_page_description")).toBeVisible();

    await page.getByTestId("new_project_btn_empty_page").click();

    await page.getByTestId("side_nav_options_all-templates").click();
    await page.getByRole("heading", { name: "Basic Prompting" }).click();

    await page.waitForSelector('[data-testid="icon-ChevronLeft"]', {
      timeout: 100000,
    });

    await page.getByTestId("icon-ChevronLeft").first().click();

    await page.waitForSelector('[data-testid="home-dropdown-menu"]', {
      timeout: 100000,
    });

    await expect(page.getByTestId("get_started_progress_title")).toBeVisible();
    await expect(
      page.getByTestId("github_starred_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("create_flow_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("discord_joined_icon_get_started"),
    ).not.toBeVisible();
    await expect(
      page.getByTestId("get_started_progress_percentage").first(),
    ).toHaveText("66%");

    await page.getByTestId("discord_joined_btn_get_started").click();
    const pagePromiseDiscord = context.waitForEvent("page");

    const newPageDiscord = await pagePromiseDiscord;
    await newPageDiscord.waitForTimeout(3000);
    const newUrlDiscord = newPageDiscord.url();

    await expect(newUrlDiscord).toContain(DISCORD_URL);

    await newPageDiscord.close();

    await expect(page.getByTestId("app-header")).toBeVisible();
    await expect(
      page.getByTestId("discord_joined_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("create_flow_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("github_starred_icon_get_started"),
    ).toBeVisible();
    await expect(
      page.getByTestId("get_started_progress_percentage").first(),
    ).toHaveText("100%");

    await page.getByTestId("close_get_started_dialog").click();

    await expect(
      page.getByTestId("discord_joined_icon_get_started"),
    ).not.toBeVisible();
    await expect(
      page.getByTestId("create_flow_icon_get_started"),
    ).not.toBeVisible();
    await expect(
      page.getByTestId("github_starred_icon_get_started"),
    ).not.toBeVisible();
  },
);
