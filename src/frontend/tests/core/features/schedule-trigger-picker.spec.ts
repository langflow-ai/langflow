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

async function addScheduleNode(page: LangflowPage): Promise<string> {
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
  return flowId!;
}

function triggerConfig(page: LangflowPage, flowId: string) {
  return async () => {
    const response = await page.request.get(
      `/api/v1/triggers?flow_id=${flowId}`,
    );
    const [trigger] = await response.json();
    return trigger?.config;
  };
}

async function typeTime(page: LangflowPage, testId: string, time: string) {
  const input = page.getByTestId(testId);
  await input.fill(time);
  await input.press("Enter");
}

// Intl separates "5:30" and "PM" with a narrow no-break space.
const clock = (text: string) => new RegExp(`^${text.replace(" ", "\\s")}$`);

test(
  "user schedules a flow at several times a day without writing a cron expression",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    const flowId = await addScheduleNode(page);
    const config = triggerConfig(page, flowId);
    const cron = page.getByTestId("popover-anchor-input-cron_expression");
    const firstTime = page.getByTestId("timeofday_str_times_of_day_0");
    const secondTime = page.getByTestId("timeofday_str_times_of_day_1");

    await expect(
      page.getByTestId("value-dropdown-dropdown_str_schedule_type"),
    ).toHaveText("Weekly");
    await expect(cron).toHaveCount(0);

    await pickOption(page, "schedule_type", "Daily");
    await expect(firstTime).toHaveValue(clock("8:00 AM"));
    await typeTime(page, "timeofday_str_times_of_day_0", "17:30");
    await expect(firstTime).toHaveValue(clock("5:30 PM"));
    await page.getByTestId("timeofday_str_times_of_day_add").click();
    await typeTime(page, "timeofday_str_times_of_day_1", "8:15 am");
    await pickOption(page, "timezone", "Europe/Lisbon");
    await page.runA11yScan("schedule-trigger-picker-daily");

    await expect.poll(config, { timeout: 30_000 }).toMatchObject({
      crons: ["15 8 * * *", "30 17 * * *"],
      timezone: "Europe/Lisbon",
    });

    await page.reload();
    await adjustScreenView(page);
    await expect(firstTime).toHaveValue(clock("5:30 PM"));
    await expect(secondTime).toHaveValue(clock("8:15 AM"));

    // The server compiles the pick; the cron field keeps the expression the user last typed.
    await pickOption(page, "schedule_type", "Custom (cron)");
    await expect(cron).toHaveValue("0 8 * * 1-5");
  },
);

test(
  "user schedules a flow to run once, or every few minutes",
  { tag: ["@release", "@workspace", "@api"] },
  async ({ page }) => {
    const flowId = await addScheduleNode(page);
    const config = triggerConfig(page, flowId);

    await pickOption(page, "schedule_type", "Once");
    await page.getByTestId("datetime_str_run_at_date").fill("2030-01-15");
    await typeTime(page, "datetime_str_run_at_time", "9:45 PM");
    await page.runA11yScan("schedule-trigger-picker-once");
    await expect
      .poll(config, { timeout: 30_000 })
      .toMatchObject({ run_at: "2030-01-15T21:45" });

    await pickOption(page, "schedule_type", "At regular intervals");
    const minutes = page.getByTestId("int_int_interval_minutes");
    await minutes.fill("7");
    await minutes.blur();
    await expect
      .poll(config, { timeout: 30_000 })
      .toMatchObject({ interval_minutes: 7 });
  },
);

test(
  "the picker's choices are shown in the interface language",
  { tag: ["@release", "@workspace"] },
  async ({ page }) => {
    const flowId = await addScheduleNode(page);
    await expect
      .poll(triggerConfig(page, flowId), { timeout: 30_000 })
      .toBeTruthy();
    // Switched after the bootstrap, which looks for English labels.
    await page.evaluate(() => {
      localStorage.setItem("languagePreference", "zh-Hans");
    });
    await page.reload();
    await adjustScreenView(page);

    await expect(
      page.getByTestId("value-dropdown-dropdown_str_schedule_type"),
    ).toHaveText("每周");
    await expect(
      page.getByTestId("value-dropdown-multiselect_str_days_of_week"),
    ).toHaveText("星期一, 星期二, 星期三, 星期四, 星期五");

    await page.getByTestId("dropdown_str_schedule_type").click();
    await expect(page.getByTestId("Once-1-option")).toHaveText("仅一次");
    await page.getByTestId("Daily-2-option").click();
    await expect(
      page.getByTestId("value-dropdown-dropdown_str_schedule_type"),
    ).toHaveText("每天");
    await expect(page.getByTestId("timeofday_str_times_of_day_0")).toHaveValue(
      "8:00",
    );
  },
);
