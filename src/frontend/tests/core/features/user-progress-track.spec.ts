import { expect, test } from "@playwright/test";
import { DISCORD_URL, GITHUB_URL } from "../../../src/constants/constants";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";

test(
  "user must be able to track their progress in getting started",
  { tag: ["@release", "@api"] },
  async ({ page }) => {
    await page.goto("/");

    let emptyButton = page.getByTestId("new_project_btn_empty_page");
    while ((await emptyButton.count()) === 0) {
      await page.getByTestId("home-dropdown-menu").click();
      await page.getByTestId("btn_delete_dropdown_menu").click();
      await page.getByTestId("btn_delete_delete_confirmation_modal").click();
      await page.waitForTimeout(1000);
      emptyButton = page.getByTestId("new_project_btn_empty_page");
    }

    await expect(emptyButton).toBeVisible();
    await expect(page.getByTestId("empty_page_title")).toBeVisible();
    await expect(page.getByTestId("empty_page_description")).toBeVisible();
    await expect(page.getByTestId("empty_page_github_button")).toBeVisible();
    await expect(page.getByTestId("empty_page_discord_button")).toBeVisible();
    await expect(
      page.getByTestId("empty_page_drag_and_drop_text"),
    ).toBeVisible();
    await expect(page.getByTestId("app-header")).not.toBeVisible();

    await page.getByTestId("empty_page_github_button").click();

    await expect(page).toHaveURL(GITHUB_URL);

    await page.close();

    await page.goto("/");

    await expect(page.getByTestId("empty_page_title")).toBeVisible();
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

    await expect(page.getByTestId("app-header")).toBeVisible();
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
    await expect(page).toHaveURL(DISCORD_URL);

    await page.close();

    await page.goto("/");

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

    await page.waitForTimeout(10000000);
  },
);
