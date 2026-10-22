import { expect, type LangflowPage, test } from "../../fixtures";
import { awaitBootstrapTest } from "../../utils/await-bootstrap-test";
import {
  buildMockConnection,
  buildMockTrigger,
  CONNECTION_NOT_AUTHORIZED_ERROR,
  installTriggerMocks,
} from "../../utils/trigger-mocks";

const SLACK_TRIGGER_ID = "trg-slack-e2e";
const SLACK_CONNECTION_ID = "conn-slack-e2e";

async function openTriggersSettings(page: LangflowPage) {
  await awaitBootstrapTest(page, { skipModal: true });
  await page.goto("/settings/triggers");
  await expect(
    page.getByRole("heading", { name: "Triggers", exact: true }),
  ).toBeVisible();
}

test.describe("Provider trigger (mocked Slack)", () => {
  test(
    "finds older triggers and providers beyond the first settings page",
    { tag: ["@release", "@workspace", "@api"] },
    async ({ page }) => {
      const recent = Array.from({ length: 200 }, (_, index) =>
        buildMockTrigger({
          id: `recent-${index}`,
          name: `Recent Slack ${index}`,
          provider: "slack",
          kind: "slack.message",
        }),
      );
      await installTriggerMocks(page, {
        triggers: [
          ...recent,
          buildMockTrigger({
            id: "older-google",
            name: "Older Gmail",
            provider: "google",
            kind: "google.gmail",
          }),
        ],
      });
      await openTriggersSettings(page);
      await page.getByTestId("triggers-search").fill("Older Gmail");
      await expect(page.getByTestId("trigger-row-older-google")).toBeVisible();
      await page.getByRole("tab", { name: "All triggers" }).click();
      await page.getByTestId("triggers-provider-filter").click();
      await page.getByRole("option", { name: "Google", exact: true }).click();
      await expect(page.getByTestId("trigger-row-older-google")).toBeVisible();
      await expect(page.getByTestId("triggers-bulk-pause")).toBeEnabled();
    },
  );

  test(
    "owner grants background runs, the subscription converges, then test, pause, resume and delete",
    { tag: ["@release", "@workspace", "@api"] },
    async ({ page }) => {
      const server = await installTriggerMocks(page, {
        // The provider answers `pending` for two polls after enable, the way
        // a subscription takes a moment to land.
        subscribePolls: 2,
        connections: [buildMockConnection({ id: SLACK_CONNECTION_ID })],
        triggers: [
          buildMockTrigger({
            id: SLACK_TRIGGER_ID,
            flow_name: "Support triage",
            name: "New Slack message",
            kind: "slack.message",
            provider: "slack",
            connection_id: SLACK_CONNECTION_ID,
            config: { mechanism: "slack.events_api" },
            state: "needs_reconnect",
            last_error: CONNECTION_NOT_AUTHORIZED_ERROR,
          }),
        ],
      });
      await openTriggersSettings(page);

      const row = page.getByTestId(`trigger-row-${SLACK_TRIGGER_ID}`);
      await expect(row).toContainText("Support triage");
      await expect(row).toContainText("Team Slack");
      await expect(row).toContainText(
        "Allow background runs is off for this connection.",
      );

      // Consent is never granted as a side effect: the fix asks first.
      await row.getByTestId("trigger-fix-reconnect").click();
      const consent = page.getByTestId("trigger-consent-dialog");
      await expect(consent).toContainText("Allow background runs?");
      expect(server.writes).toEqual([]);
      await page.getByTestId("trigger-consent-confirm").click();
      await expect(consent).toBeHidden();
      expect(server.writes).toEqual([
        `PATCH /connections/${SLACK_CONNECTION_ID}`,
        `POST /triggers/${SLACK_TRIGGER_ID}/enable`,
      ]);
      expect(
        server.connections.get(SLACK_CONNECTION_ID)?.allow_non_interactive,
      ).toBe(true);

      // Polling carries the row from pending to active with no reload.
      await expect(row).toContainText("Pending");
      await expect(row).toContainText("Active", { timeout: 15_000 });

      // A healthy connection keeps Reconnect visible but refused, with why.
      await page.getByTestId(`trigger-menu-${SLACK_TRIGGER_ID}`).click();
      const reconnect = page.getByTestId("trigger-action-reconnect");
      await expect(reconnect).toHaveAttribute("aria-disabled", "true");
      await expect(reconnect).toContainText(
        "The connection is healthy. Reconnect turns on when access is revoked.",
      );
      await page.keyboard.press("Escape");

      // Test, then see the event in the drawer.
      await page.getByTestId(`trigger-test-${SLACK_TRIGGER_ID}`).click();
      await expect(
        page.getByText("Sent a test event to New Slack message"),
      ).toBeVisible();
      await page.getByTestId(`trigger-menu-${SLACK_TRIGGER_ID}`).click();
      await page.getByTestId("trigger-action-view_events").click();
      const drawer = page.getByTestId("trigger-events-drawer");
      await expect(
        drawer.getByTestId(`trigger-event-${server.events[0].id}`),
      ).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(drawer).toBeHidden();

      // Pause, resume, delete.
      await page.getByTestId(`trigger-menu-${SLACK_TRIGGER_ID}`).click();
      await page.getByTestId("trigger-action-pause").click();
      await expect(row).toContainText(
        "Paused. Resume to start listening again.",
      );

      await row.getByTestId("trigger-fix-resume").click();
      await expect(row).toContainText("Active", { timeout: 15_000 });

      await page.getByTestId(`trigger-menu-${SLACK_TRIGGER_ID}`).click();
      await page.getByTestId("trigger-action-delete").click();
      await page.getByTestId("btn_delete_delete_confirmation_modal").click();
      await expect(row).toBeHidden();

      expect(server.writes.slice(2)).toEqual([
        `POST /triggers/${SLACK_TRIGGER_ID}/test`,
        `POST /triggers/${SLACK_TRIGGER_ID}/disable`,
        `POST /triggers/${SLACK_TRIGGER_ID}/enable`,
        `DELETE /triggers/${SLACK_TRIGGER_ID}`,
      ]);
    },
  );

  test(
    "operator pauses every Slack trigger after a dry run, and resumes only the admin-paused ones",
    { tag: ["@release", "@workspace", "@api"] },
    async ({ page }) => {
      const server = await installTriggerMocks(page, {
        triggers: [
          buildMockTrigger({
            id: "trg-slack-a",
            flow_name: "Support triage",
            name: "New Slack message",
            kind: "slack.message",
            provider: "slack",
            state: "active",
            user_id: "user-a",
            owner_username: "ana",
          }),
          buildMockTrigger({
            id: "trg-slack-b",
            flow_name: "Release notes",
            name: "Slack reaction",
            kind: "slack.reaction",
            provider: "slack",
            state: "active",
            user_id: "user-b",
            owner_username: "bo",
          }),
          buildMockTrigger({
            id: "trg-slack-owner-paused",
            flow_name: "Quiet channel",
            name: "Slack reaction",
            kind: "slack.reaction",
            provider: "slack",
            state: "paused",
            user_id: "user-b",
            owner_username: "bo",
          }),
          buildMockTrigger({
            id: "trg-google",
            flow_name: "Inbox digest",
            name: "New Gmail message",
            kind: "google.gmail_message",
            provider: "google",
            state: "active",
            user_id: "user-a",
            owner_username: "ana",
          }),
        ],
      });
      await openTriggersSettings(page);
      await page.getByRole("tab", { name: "All triggers" }).click();
      await expect(page.getByTestId("triggers-table-all")).toContainText("ana");

      // Bulk actions need a provider: nothing instance-wide by accident.
      await expect(page.getByTestId("triggers-bulk-pause")).toBeDisabled();
      await page.getByTestId("triggers-provider-filter").click();
      await page.getByRole("option", { name: "Slack" }).click();
      await expect(page.getByTestId("trigger-row-trg-google")).toBeHidden();

      await page.getByTestId("triggers-bulk-pause").click();
      const dialog = page.getByTestId("triggers-bulk-dialog");
      // The counts come from the server's dry run, before anything changes.
      await expect(dialog).toContainText("Pause 2 active Slack triggers?");
      expect(server.bulkBodies).toEqual([{ provider: "slack", dry_run: true }]);
      expect(server.triggers.get("trg-slack-a")?.state).toBe("active");

      await page.getByTestId("triggers-bulk-confirm").click();
      await expect(dialog).toBeHidden();
      await expect(page.getByTestId("trigger-row-trg-slack-a")).toContainText(
        "Paused",
      );
      await expect(page.getByTestId("trigger-row-trg-slack-b")).toContainText(
        "Paused",
      );
      expect(server.triggers.get("trg-google")?.state).toBe("active");

      // Resume only undoes the admin pause; the owner's own pause stays.
      await page.getByTestId("triggers-bulk-resume").click();
      await expect(dialog).toContainText(
        "Resume 2 Slack triggers paused by an admin?",
      );
      await page.getByTestId("triggers-bulk-confirm").click();
      await expect(page.getByTestId("trigger-row-trg-slack-a")).toContainText(
        "Active",
      );
      expect(server.triggers.get("trg-slack-owner-paused")?.state).toBe(
        "paused",
      );
      // Each change is the dry run's twin minus the flag, so it acts on the
      // set the operator just confirmed.
      expect(server.bulkBodies).toEqual([
        { provider: "slack", dry_run: true },
        { provider: "slack" },
        { provider: "slack", dry_run: true },
        { provider: "slack" },
      ]);
    },
  );
});
