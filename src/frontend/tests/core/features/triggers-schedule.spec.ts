import { expect, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  placeScheduleTrigger,
  searchPalette,
} from "../../utils/trigger-canvas";
import {
  buildMockTrigger,
  installTriggerMocks,
  type MockTriggerEvent,
} from "../../utils/trigger-mocks";

const TRIGGER_ID = "trg-schedule-e2e";

test.describe("Schedule trigger lifecycle", () => {
  test(
    "user can enable, test, inspect, replay, pause, resume and delete a schedule trigger",
    { tag: ["@release", "@workspace", "@api"] },
    async ({ page }) => {
      const server = await installTriggerMocks(page);
      const node = await placeScheduleTrigger(page, server, {
        triggerId: TRIGGER_ID,
        flowName: "Daily digest",
      });

      // The next poll picks the reconciled row up: pending, switch off.
      const badge = node.getByTestId("trigger-node-badge");
      await expect(badge).toHaveAttribute("data-state", "pending", {
        timeout: 10_000,
      });
      const enabled = node.getByTestId("trigger-node-enabled");
      await expect(enabled).toHaveAttribute("aria-checked", "false");

      // One trigger per flow: the other trigger is unavailable in the palette.
      await searchPalette(page, "webhook");
      await page.getByTestId("triggers_inbound webhook_draggable").hover();
      await expect(
        page.getByText(
          "This flow already has a trigger. A flow has one trigger.",
        ),
      ).toBeVisible();

      // Enable
      await enabled.click();
      await expect(badge).toHaveAttribute("data-state", "active");
      await expect(enabled).toHaveAttribute("aria-checked", "true");
      expect(server.writes).toContain(`POST /triggers/${TRIGGER_ID}/enable`);

      // Test from the badge popover
      await badge.click();
      const popover = page.getByTestId("trigger-node-popover");
      await expect(popover).toBeVisible();
      await popover.getByTestId("trigger-node-test").click();
      await expect(
        page.getByText("Sent a test event to Schedule"),
      ).toBeVisible();

      // See the run in the events drawer
      await popover.getByTestId("trigger-node-events").click();
      const drawer = page.getByTestId("trigger-events-drawer");
      await expect(drawer).toBeVisible();
      await expect(
        drawer.getByRole("heading", { name: /Daily digest/ }),
      ).toBeVisible();
      const [testEvent] = server.events;
      await expect(
        drawer.getByTestId(`trigger-event-${testEvent.id}`),
      ).toBeVisible();
      await expect(drawer.getByTestId("trigger-event-payload")).toContainText(
        '"test": true',
      );

      // Replay creates a new linked event; the original is left as it was.
      await drawer.getByTestId("trigger-event-replay").click();
      await page.getByTestId("trigger-replay-confirm").click();
      await expect(
        page.getByText("Replay queued as a new event"),
      ).toBeVisible();
      const replayed = server.events[0];
      expect(replayed.replay_of_event_id).toBe(testEvent.id);
      await expect(
        drawer.getByTestId(`trigger-event-${replayed.id}`),
      ).toBeVisible();
      await expect(
        drawer.getByTestId(`trigger-event-${testEvent.id}`),
      ).toBeVisible();
      await expect(drawer.getByTestId("trigger-event-lineage")).toContainText(
        "Replay of",
      );
      await drawer.getByTestId("trigger-events-filter-replays").click();
      await expect(
        drawer.getByTestId(`trigger-event-${testEvent.id}`),
      ).toBeHidden();
      await page.keyboard.press("Escape");
      await expect(drawer).toBeHidden();

      // Pause from the node
      await enabled.click();
      await expect(badge).toHaveAttribute("data-state", "paused");
      await expect(enabled).toHaveAttribute("aria-checked", "false");

      // Resume and delete from Settings › Triggers
      await page.goto("/settings/triggers");
      const row = page.getByTestId(`trigger-row-${TRIGGER_ID}`);
      await expect(row).toContainText("Daily digest");
      await expect(row).toContainText("Paused");

      await page.getByTestId(`trigger-menu-${TRIGGER_ID}`).click();
      // Pause does not apply to a paused trigger, so it is not offered.
      await expect(page.getByTestId("trigger-action-pause")).toHaveCount(0);
      await page.getByTestId("trigger-action-resume").click();
      await expect(row).toContainText("Active");
      await expect(page.getByText("Resumed Schedule")).toBeVisible();

      await page.getByTestId(`trigger-menu-${TRIGGER_ID}`).click();
      await page.getByTestId("trigger-action-delete").click();
      await page.getByTestId("btn_delete_delete_confirmation_modal").click();
      await expect(row).toBeHidden();
      await expect(page.getByTestId("triggers-empty")).toBeVisible();

      expect(server.writes).toEqual([
        `POST /triggers/${TRIGGER_ID}/enable`,
        `POST /triggers/${TRIGGER_ID}/test`,
        `POST /triggers/${TRIGGER_ID}/replay`,
        `POST /triggers/${TRIGGER_ID}/disable`,
        `POST /triggers/${TRIGGER_ID}/enable`,
        `DELETE /triggers/${TRIGGER_ID}`,
      ]);
    },
  );

  test(
    "test and replay stay visible but blocked on a paused schedule trigger",
    { tag: ["@release", "@workspace", "@api"] },
    async ({ page }) => {
      const server = await installTriggerMocks(page, {
        triggers: [
          buildMockTrigger({
            id: TRIGGER_ID,
            flow_name: "Daily digest",
            state: "paused",
          }),
        ],
        events: [
          {
            id: "evt-old",
            trigger_id: TRIGGER_ID,
            dedupe_key: "schedule:2026-10-15T09:00:00Z",
            state: "failed",
            attempt: 5,
            available_at: null,
            payload: { fired_at: "2026-10-15T09:00:00Z" },
            session_id: null,
            job_id: null,
            replay_of_event_id: null,
            error: "flow_build_failed",
            created_at: "2026-10-15T09:00:00Z",
            updated_at: "2026-10-15T09:00:05Z",
          },
        ],
      });
      await awaitBootstrapTest(page, { skipModal: true });
      await page.goto("/settings/triggers");

      const testButton = page.getByTestId(`trigger-test-${TRIGGER_ID}`);
      await expect(testButton).toHaveAttribute("aria-disabled", "true");
      await testButton.hover();
      await expect(page.getByRole("tooltip")).toContainText(
        "Resume the trigger first.",
      );
      await testButton.click({ force: true });

      await page.getByTestId(`trigger-menu-${TRIGGER_ID}`).click();
      await page.getByTestId("trigger-action-view_events").click();
      const replay = page.getByTestId("trigger-event-replay");
      await expect(replay).toHaveAttribute("aria-disabled", "true");
      await replay.hover();
      await expect(page.getByRole("tooltip")).toContainText(
        "Resume the trigger first.",
      );
      await replay.click({ force: true });
      await expect(page.getByTestId("trigger-replay-dialog")).toBeHidden();

      // Neither refused action reached the server.
      expect(server.writes).toEqual([]);
    },
  );

  test(
    "loads older failed events beyond 200 rows",
    { tag: ["@release", "@workspace", "@api"] },
    async ({ page }) => {
      const events: MockTriggerEvent[] = Array.from(
        { length: 220 },
        (_, index) => ({
          id: `history-${index}`,
          trigger_id: TRIGGER_ID,
          dedupe_key: `schedule:${index}`,
          state: index === 219 ? "failed" : "completed",
          attempt: 1,
          available_at: null,
          payload: { text: `Event ${index}` },
          session_id: null,
          job_id: null,
          replay_of_event_id: null,
          error: index === 219 ? "job_failed" : null,
          created_at: "2026-10-15T09:00:00Z",
          updated_at: "2026-10-15T09:00:05Z",
        }),
      );
      await installTriggerMocks(page, {
        triggers: [buildMockTrigger({ id: TRIGGER_ID })],
        events,
      });
      await awaitBootstrapTest(page, { skipModal: true });
      await page.goto("/settings/triggers");
      await page.getByTestId(`trigger-menu-${TRIGGER_ID}`).click();
      await page.getByTestId("trigger-action-view_events").click();
      await page.getByTestId("trigger-events-filter-failed").click();
      for (let index = 0; index < 4; index++) {
        const older = page.getByTestId("trigger-events-load-more");
        await expect(older).not.toHaveAttribute("aria-busy", "true");
        await older.click();
      }
      await expect(page.getByTestId("trigger-event-history-219")).toBeVisible();
      await expect(page.getByTestId("trigger-events-load-more")).toBeHidden();
      await page.runA11yScan("settings-triggers-older-failed-event");
    },
  );
});
