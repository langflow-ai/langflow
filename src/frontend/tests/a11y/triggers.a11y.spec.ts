import { expect, type LangflowPage, test } from "../fixtures";
import { awaitBootstrapTest } from "../utils/await-bootstrap-test";
import { TIMEOUTS } from "../utils/constants/timeouts";
import { placeScheduleTrigger } from "../utils/trigger-canvas";
import {
  buildMockConnection,
  buildMockTrigger,
  CONNECTION_NOT_AUTHORIZED_ERROR,
  installTriggerMocks,
  type MockTriggerEvent,
  type TriggerMockOptions,
} from "../utils/trigger-mocks";

const SCHEDULE_ID = "a11y-schedule";
const WEBHOOK_ID = "a11y-webhook";
const SLACK_ID = "a11y-slack";
const SLACK_HEALTHY_ID = "a11y-slack-healthy";
const SLACK_CONNECTION_ID = "a11y-conn-slack";

const failedEvent: MockTriggerEvent = {
  id: "a11y-evt-failed",
  trigger_id: SCHEDULE_ID,
  dedupe_key: "schedule:2026-10-15T09:00:00Z",
  state: "failed",
  attempt: 5,
  available_at: null,
  payload: { fired_at: "2026-10-15T09:00:00Z" },
  session_id: "a11y-session",
  job_id: "a11y-job",
  replay_of_event_id: null,
  error: "flow_build_failed",
  created_at: "2026-10-15T09:00:00Z",
  updated_at: "2026-10-15T09:00:05Z",
};

/** One row per surface the page has to explain: running, refused, fixable. */
const showcase: TriggerMockOptions = {
  connections: [buildMockConnection({ id: SLACK_CONNECTION_ID })],
  triggers: [
    buildMockTrigger({
      id: SCHEDULE_ID,
      flow_name: "Daily digest",
      state: "active",
      next_fire_at: "2026-10-17T09:00:00Z",
      last_fired_at: "2026-10-15T09:00:00Z",
    }),
    buildMockTrigger({
      id: WEBHOOK_ID,
      flow_name: "Partner intake",
      name: "Inbound Webhook",
      kind: "inbound_webhook",
      provider: "webhook",
      config: {},
      state: "paused",
    }),
    buildMockTrigger({
      id: SLACK_ID,
      flow_name: "Support triage",
      name: "New Slack message",
      kind: "slack.message",
      provider: "slack",
      connection_id: SLACK_CONNECTION_ID,
      config: { mechanism: "slack.events_api" },
      state: "needs_reconnect",
      last_error: CONNECTION_NOT_AUTHORIZED_ERROR,
    }),
    buildMockTrigger({
      id: SLACK_HEALTHY_ID,
      flow_name: "Release notes",
      name: "Slack reaction",
      kind: "slack.reaction",
      provider: "slack",
      connection_id: SLACK_CONNECTION_ID,
      config: { mechanism: "slack.events_api" },
      state: "active",
    }),
  ],
  events: [failedEvent],
};

async function disableAnimations(page: LangflowPage) {
  await page.addStyleTag({
    content: `
      *,
      *::before,
      *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        scroll-behavior: auto !important;
      }
    `,
  });
}

async function openTriggersRoute(
  page: LangflowPage,
  options: TriggerMockOptions = showcase,
) {
  const server = await installTriggerMocks(page, options);
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/triggers");
  await disableAnimations(page);
  await expect(page.getByTestId("triggers-search")).toBeVisible({
    timeout: TIMEOUTS.standard,
  });
  return server;
}

test.describe("Triggers route accessibility", () => {
  test(
    "scans the populated triggers table",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openTriggersRoute(page);
      await expect(page.getByTestId(`trigger-row-${SLACK_ID}`)).toBeVisible();

      await page.runA11yScan("settings-triggers-data-rich");
    },
  );

  test(
    "scans the empty triggers page",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openTriggersRoute(page, {});
      await expect(page.getByTestId("triggers-empty")).toBeVisible();

      await page.runA11yScan("settings-triggers-empty");
    },
  );

  test(
    "row menu opens from the keyboard and keeps refused actions reachable",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openTriggersRoute(page);

      const menuButton = page.getByTestId(`trigger-menu-${SLACK_HEALTHY_ID}`);
      await menuButton.focus();
      await page.keyboard.press("Enter");

      // The connection is healthy, so Reconnect is shown but refused, with a
      // reason a screen reader reads from aria-describedby.
      const menu = page.getByRole("menu");
      await expect(menu).toBeVisible();
      const items = menu.getByRole("menuitem");
      const names = await items.allInnerTexts();
      expect(names.map((name) => name.trim())).toEqual(
        expect.arrayContaining(["View events", "Pause", "Delete"]),
      );

      const refused = menu.locator('[role="menuitem"][aria-disabled="true"]');
      await expect(refused).toHaveCount(1);
      await expect(refused).toContainText("Reconnect");
      for (const item of await refused.all()) {
        const describedBy = await item.getAttribute("aria-describedby");
        expect(describedBy, "a refused action names its reason").toBeTruthy();
        await expect(page.locator(`[id="${describedBy}"]`)).not.toBeEmpty();
      }

      await page.runA11yScan("settings-triggers-row-menu");

      // Arrow keys walk every item, refused ones included.
      const focusedTestId = () =>
        page.evaluate(() =>
          document.activeElement?.getAttribute("data-testid"),
        );
      const visited = [await focusedTestId()];
      const count = await items.count();
      for (let index = 1; index < count; index += 1) {
        const previous = visited[visited.length - 1];
        await page.keyboard.press("ArrowDown");
        await expect.poll(focusedTestId).not.toBe(previous);
        visited.push(await focusedTestId());
      }
      expect(visited).toContain("trigger-action-reconnect");
      expect(visited).toContain("trigger-action-delete");

      await page.keyboard.press("Escape");
      await expect(menu).toBeHidden();
      await expect(menuButton).toBeFocused();
    },
  );

  test(
    "events drawer is a labelled dialog with pressed-state filters and a keyboard replay",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      const server = await openTriggersRoute(page);

      await page.getByTestId(`trigger-menu-${SCHEDULE_ID}`).focus();
      await page.keyboard.press("Enter");
      await page.getByTestId("trigger-action-view_events").focus();
      await page.keyboard.press("Enter");

      const drawer = page.getByRole("dialog", { name: /Daily digest/ });
      await expect(drawer).toBeVisible();
      await expect(
        drawer.getByTestId(`trigger-event-${failedEvent.id}`),
      ).toBeVisible();

      const all = drawer.getByTestId("trigger-events-filter-all");
      const failed = drawer.getByTestId("trigger-events-filter-failed");
      await expect(all).toHaveAttribute("aria-pressed", "true");
      await failed.focus();
      await page.keyboard.press("Space");
      await expect(failed).toHaveAttribute("aria-pressed", "true");
      await expect(all).toHaveAttribute("aria-pressed", "false");

      // The payload wraps rather than scrolling inside its own box, so it
      // needs no tab stop of its own; the detail pane scrolls it.
      await expect(
        drawer.getByTestId("trigger-event-payload"),
      ).not.toHaveAttribute("tabindex");

      await page.runA11yScan("settings-triggers-events-drawer");

      await drawer.getByTestId("trigger-event-replay").focus();
      await page.keyboard.press("Enter");
      const confirm = page.getByRole("dialog", { name: "Replay this event?" });
      await expect(confirm).toBeVisible();
      await page.runA11yScan("settings-triggers-replay-confirm");
      await page.getByTestId("trigger-replay-confirm").focus();
      await page.keyboard.press("Enter");
      await expect(confirm).toBeHidden();
      await expect(drawer.getByTestId("trigger-event-lineage")).toContainText(
        "Replay of",
      );
      expect(server.events[0].replay_of_event_id).toBe(failedEvent.id);

      await page.keyboard.press("Escape");
      await expect(drawer).toBeHidden();
    },
  );

  test(
    "consent, delete and signing-secret dialogs scan clean and close with Escape",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openTriggersRoute(page);

      await page
        .getByTestId(`trigger-row-${SLACK_ID}`)
        .getByTestId("trigger-fix-reconnect")
        .click();
      const consent = page.getByRole("dialog", {
        name: "Allow background runs?",
      });
      await expect(consent).toBeVisible();
      await page.runA11yScan("settings-triggers-consent-dialog");
      await page.keyboard.press("Escape");
      await expect(consent).toBeHidden();

      await page.getByTestId(`trigger-menu-${WEBHOOK_ID}`).click();
      await page.getByTestId("trigger-action-rotate_secret").click();
      const secret = page.getByTestId("trigger-secret-dialog");
      await expect(secret).toBeVisible();
      await page.getByTestId("trigger-secret-rotate").click();
      await expect(page.getByTestId("trigger-secret-value")).toBeVisible();
      await page.runA11yScan("settings-triggers-secret-revealed");
      await page.keyboard.press("Escape");
      await expect(secret).toBeHidden();

      await page.getByTestId(`trigger-menu-${SCHEDULE_ID}`).click();
      await page.getByTestId("trigger-action-delete").click();
      const deletion = page.getByRole("dialog");
      await expect(
        page.getByTestId("btn_delete_delete_confirmation_modal"),
      ).toBeVisible();
      await page.runA11yScan("settings-triggers-delete-dialog");
      await page.keyboard.press("Escape");
      await expect(deletion).toBeHidden();
    },
  );

  test(
    "operator bulk dialog scans clean with dry-run counts",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await openTriggersRoute(page);
      await page.getByRole("tab", { name: "All triggers" }).click();
      await page.getByTestId("triggers-provider-filter").click();
      await page.getByRole("option", { name: "Slack" }).click();
      await page.getByTestId("triggers-bulk-pause").click();
      const dialog = page.getByTestId("triggers-bulk-dialog");
      await expect(dialog).toContainText("Pause 2 active Slack triggers?");

      await page.runA11yScan("settings-triggers-bulk-dialog");
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
    },
  );

  test(
    "scans the triggers table on mobile width",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openTriggersRoute(page);
      await expect(
        page.getByTestId(`trigger-row-${SCHEDULE_ID}`),
      ).toBeVisible();

      await page.runA11yScan("settings-triggers-mobile-data-rich");
    },
  );
});

test.describe("Trigger node badge accessibility", () => {
  test(
    "badge popover opens from the keyboard, names the state and returns focus",
    { tag: ["@release", "@workspace"] },
    async ({ page }) => {
      const server = await installTriggerMocks(page);
      const node = await placeScheduleTrigger(page, server, {
        triggerId: SCHEDULE_ID,
        flowName: "Daily digest",
      });

      const badge = node.getByTestId("trigger-node-badge");
      await expect(badge).toHaveAccessibleName(
        "Trigger state: Pending. Show details.",
      );
      await badge.focus();
      await page.keyboard.press("Enter");
      const popover = page.getByTestId("trigger-node-popover");
      await expect(popover).toBeVisible();
      await expect(popover).toContainText(
        "Not listening yet. Turn on Enabled to start",
      );

      await page.runA11yScan("canvas-trigger-badge-popover");

      await page.keyboard.press("Escape");
      await expect(popover).toBeHidden();
      await expect(badge).toBeFocused();

      // The Enabled switch is a named switch the keyboard can flip. Enter, not
      // Space: the canvas "open code" shortcut binds Space with
      // `preventDefault: true` while a node is selected (use-shortcuts.ts).
      const enabled = node.getByRole("switch", { name: "Enabled" });
      await enabled.focus();
      await page.keyboard.press("Enter");
      await expect(badge).toHaveAccessibleName(
        "Trigger state: Active. Show details.",
      );
    },
  );
});
