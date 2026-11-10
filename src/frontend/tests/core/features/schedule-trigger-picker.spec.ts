import { expect, type LangflowPage, test } from "../../fixtures";
import { adjustScreenView } from "../../utils/adjust-screen-view";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import { searchPalette } from "../../utils/trigger-canvas";

async function pickOption(page: LangflowPage, field: string, option: string) {
  await page.getByTestId(`dropdown_str_${field}`).click();
  await page
    .locator(`[data-testid^="${option}-"][data-testid$="-option"]`)
    .first()
    .click();
  await expect(
    page.getByTestId(`value-dropdown-dropdown_str_${field}`),
  ).toHaveText(option);
}

test(
  "user schedules a flow with the picker instead of writing a cron expression",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("langflow-assistant-discovered", "true");
    });
    await awaitBootstrapTest(page);
    await page.getByTestId("blank-flow").click();
    await searchPalette(page, "schedule");
    await page.getByTestId("add-component-button-schedule").click();
    await adjustScreenView(page);
    const flowId = new URL(page.url()).pathname.match(/\/flow\/([^/]+)/)?.[1];
    expect(flowId, "flow id should be in the URL").toBeTruthy();

    const cron = page.getByTestId("popover-anchor-input-cron_expression");
    await expect(
      page.getByTestId("value-dropdown-dropdown_str_schedule_type"),
    ).toHaveText("Weekly");
    await expect(cron).toHaveCount(0);

    await pickOption(page, "schedule_type", "Daily");
    await expect(page.getByTestId("dropdown_str_time_of_day")).toBeVisible();
    await pickOption(page, "time_of_day", "17:30");
    await pickOption(page, "timezone", "Europe/Lisbon");
    await page.runA11yScan("schedule-trigger-picker-daily");

    await expect
      .poll(
        async () => {
          const response = await page.request.get(
            `/api/v1/triggers?flow_id=${flowId}`,
          );
          const [trigger] = await response.json();
          return trigger?.config;
        },
        { timeout: 30_000 },
      )
      .toMatchObject({ cron: "30 17 * * *", timezone: "Europe/Lisbon" });

    await pickOption(page, "schedule_type", "Custom (cron)");
    await expect(cron).toHaveValue("30 17 * * *");
  },
);
