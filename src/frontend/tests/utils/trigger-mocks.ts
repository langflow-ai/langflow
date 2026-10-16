import type { Page, Route } from "@playwright/test";

// ---------------------------------------------------------------------------
// Stateful fake of the triggers API for E2E tests.
//
// The fake keeps one in-memory ledger per page, so a mutation is visible to the
// next poll exactly as it would be on a real server. Capabilities follow
// `services/triggers/capabilities.py`: the UI under test renders the server's
// `allowed_actions` / `blocked_actions`, so the fake has to compute them the
// same way or the specs would pass against behaviour the server never has.
// ---------------------------------------------------------------------------

export type MockTriggerState =
  | "pending"
  | "active"
  | "paused"
  | "expired"
  | "needs_reconnect"
  | "error"
  | "dead";

export type MockTrigger = {
  id: string;
  flow_id: string;
  flow_name: string;
  user_id: string;
  owner_username: string;
  name: string;
  kind: string;
  provider: string | null;
  node_id: string | null;
  connection_id: string | null;
  config: Record<string, unknown>;
  state: MockTriggerState;
  max_attempts: number;
  next_fire_at: string | null;
  last_fired_at: string | null;
  last_error: string | null;
  admin_paused_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MockTriggerEvent = {
  id: string;
  trigger_id: string;
  dedupe_key: string;
  state: "pending" | "claimed" | "dispatched" | "completed" | "failed" | "dead";
  attempt: number;
  available_at: string | null;
  payload: Record<string, unknown>;
  session_id: string | null;
  job_id: string | null;
  replay_of_event_id: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type MockConnection = {
  id: string;
  owner_id: string;
  ownership_mode: "user" | "instance";
  provider_key: string;
  name: string;
  display_name: string;
  status: "ready";
  health: "healthy";
  granted_scopes: string[];
  executing_identity: { identity: "user_delegated" };
  allow_non_interactive: boolean;
  has_credentials: boolean;
  health_checked_at: string | null;
  created_at: string;
  updated_at: string;
};

/** Mirrors `CONNECTION_NOT_AUTHORIZED_ERROR` in services/triggers/constants.py. */
export const CONNECTION_NOT_AUTHORIZED_ERROR = "connection_not_authorized";

/** Fast enough for a spec to watch a poll land, above the client's floor. */
export const TEST_TRIGGER_POLLING_INTERVAL = 1000;

const CONNECTION_PROVIDERS = new Set(["slack", "google", "microsoft"]);
const RETIRING_STATES = new Set<MockTriggerState>([
  "paused",
  "expired",
  "dead",
]);
/** `ARMED_TRIGGER_STATES`: the rows an operator bulk pause acts on. */
const ARMED_STATES = new Set<MockTriggerState>([
  "active",
  "error",
  "needs_reconnect",
]);
const ACTION_ORDER = [
  "pause",
  "resume",
  "test",
  "reconnect",
  "replay",
  "delete",
  "rotate_secret",
] as const;
type Action = (typeof ACTION_ORDER)[number];

const NOW = "2026-10-16T09:00:00Z";
const MOCK_SIGNING_SECRET = "whsec_e2e_mock_signing_secret"; // pragma: allowlist secret

function reasonOf(row: MockTrigger): string | null {
  switch (row.state) {
    case "active":
      return row.last_error ? "degraded" : null;
    case "pending":
      return row.last_error ? "config_invalid" : "pending";
    case "paused":
      return row.admin_paused_at ? "paused_by_admin" : "paused";
    case "needs_reconnect":
      return row.last_error === CONNECTION_NOT_AUTHORIZED_ERROR
        ? "consent_required"
        : "needs_reconnect";
    case "expired":
      return "expired";
    case "dead":
      return "dead";
    default:
      return "error";
  }
}

/** Port of `trigger_capabilities` for an owner with write and execute access. */
function capabilitiesOf(row: MockTrigger) {
  const reason = reasonOf(row);
  const runBlock = RETIRING_STATES.has(row.state) ? reason : null;
  const decisions = new Map<Action, string | null>();
  if (row.state !== "paused" && row.state !== "dead") {
    decisions.set("pause", null);
  }
  if (row.state !== "active") {
    decisions.set("resume", row.state === "dead" ? "dead" : null);
  }
  decisions.set("test", runBlock);
  if (row.connection_id || CONNECTION_PROVIDERS.has(row.provider ?? "")) {
    decisions.set(
      "reconnect",
      row.state === "needs_reconnect" ? null : "reconnect_not_needed",
    );
  }
  decisions.set("replay", runBlock);
  decisions.set("delete", null);
  if (row.kind === "inbound_webhook") decisions.set("rotate_secret", null);

  const allowed: Action[] = [];
  const blocked: Partial<Record<Action, string>> = {};
  for (const action of ACTION_ORDER) {
    if (!decisions.has(action)) continue;
    const refusal = decisions.get(action);
    if (refusal == null) allowed.push(action);
    else blocked[action] = refusal;
  }
  return { reason, allowed_actions: allowed, blocked_actions: blocked };
}

export function buildMockTrigger(
  overrides: Partial<MockTrigger> & Pick<MockTrigger, "id">,
): MockTrigger {
  return {
    flow_id: "flow-e2e",
    flow_name: "E2E flow",
    user_id: "user-e2e",
    owner_username: "langflow",
    name: "Schedule",
    kind: "schedule",
    provider: null,
    node_id: null,
    connection_id: null,
    config: { cron_expression: "0 9 * * *", timezone: "UTC" },
    state: "pending",
    max_attempts: 5,
    next_fire_at: null,
    last_fired_at: null,
    last_error: null,
    admin_paused_at: null,
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

export function buildMockConnection(
  overrides: Partial<MockConnection> & Pick<MockConnection, "id">,
): MockConnection {
  return {
    owner_id: "user-e2e",
    ownership_mode: "user",
    provider_key: "slack",
    name: "team_slack",
    display_name: "Team Slack",
    status: "ready",
    health: "healthy",
    granted_scopes: [],
    executing_identity: { identity: "user_delegated" },
    allow_non_interactive: false,
    has_credentials: true,
    health_checked_at: null,
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

export type TriggerMockOptions = {
  triggers?: MockTrigger[];
  events?: MockTriggerEvent[];
  connections?: MockConnection[];
  /**
   * Polls a push source answers `pending` for after enable before it settles
   * on `active`, the way a provider subscription takes a moment to land.
   */
  subscribePolls?: number;
};

export type TriggerMockServer = {
  triggers: Map<string, MockTrigger>;
  events: MockTriggerEvent[];
  connections: Map<string, MockConnection>;
  /** `METHOD /path` of every write the UI sent, in order. */
  writes: string[];
  /** Body of every bulk request, dry runs included. */
  bulkBodies: Record<string, unknown>[];
  upsert: (trigger: MockTrigger) => void;
};

export async function installTriggerMocks(
  page: Page,
  options: TriggerMockOptions = {},
): Promise<TriggerMockServer> {
  const server: TriggerMockServer = {
    triggers: new Map((options.triggers ?? []).map((row) => [row.id, row])),
    events: [...(options.events ?? [])],
    connections: new Map(
      (options.connections ?? []).map((row) => [row.id, row]),
    ),
    writes: [],
    bulkBodies: [],
    upsert: (trigger) => server.triggers.set(trigger.id, trigger),
  };
  const secrets = new Set<string>();
  const subscribing = new Map<string, number>();
  let sequence = 0;
  const nextId = (prefix: string) => `${prefix}-${++sequence}`;
  const stamp = () =>
    new Date(Date.UTC(2026, 9, 16, 9, 0, sequence)).toISOString();

  const read = (row: MockTrigger) => ({
    ...row,
    binding_target: "draft",
    deployment_id: null,
    flow_version_id: null,
    session_policy: "per_event",
    concurrency_limit: 1,
    ...capabilitiesOf(row),
  });

  const settleSubscription = (row: MockTrigger) => {
    const left = subscribing.get(row.id);
    if (left === undefined) return;
    if (left <= 0) {
      subscribing.delete(row.id);
      row.state = "active";
      row.updated_at = stamp();
    } else {
      subscribing.set(row.id, left - 1);
    }
  };

  const addEvent = (
    row: MockTrigger,
    overrides: Partial<MockTriggerEvent>,
  ): MockTriggerEvent => {
    const id = nextId("evt");
    const created = stamp();
    const event: MockTriggerEvent = {
      id,
      trigger_id: row.id,
      dedupe_key: `${row.kind}:${id}`,
      state: "completed",
      attempt: 0,
      available_at: created,
      payload: {},
      session_id: `session-${id}`,
      job_id: `job-${id}`,
      replay_of_event_id: null,
      error: null,
      created_at: created,
      updated_at: created,
      ...overrides,
    };
    server.events.unshift(event);
    row.last_fired_at = created;
    return event;
  };

  // The real config route answers with everything else the app needs; only
  // the poll interval is tightened so specs watch convergence in seconds.
  await page.route(/\/api\/v1\/config\/?(\?.*)?$/, async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    await route.fulfill({
      response,
      json: {
        ...json,
        trigger_polling_interval: TEST_TRIGGER_POLLING_INTERVAL,
      },
    });
  });

  await page.route(
    /\/api\/v1\/connections(\/[^/?]+)?\/?(\?.*)?$/,
    async (route) => {
      const request = route.request();
      const id = new URL(request.url()).pathname.match(
        /\/connections\/([^/]+)\/?$/,
      )?.[1];
      if (request.method() === "GET" && !id) {
        await route.fulfill({ json: [...server.connections.values()] });
        return;
      }
      const connection = id ? server.connections.get(id) : undefined;
      if (request.method() === "PATCH" && connection) {
        server.writes.push(`PATCH /connections/${id}`);
        Object.assign(connection, request.postDataJSON(), {
          updated_at: stamp(),
        });
        await route.fulfill({ json: connection });
        return;
      }
      await route.fulfill({ status: 404, json: { detail: "Not found" } });
    },
  );

  await page.route(
    /\/api\/v1\/triggers(\/.*)?(\?.*)?$/,
    async (route: Route) => {
      const request = route.request();
      const method = request.method();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^.*\/api\/v1\/triggers/, "");
      const segments = path.split("/").filter(Boolean);

      if (method !== "GET") server.writes.push(`${method} /triggers${path}`);

      // Collection
      if (segments.length === 0 && method === "GET") {
        const flowId = url.searchParams.get("flow_id");
        const provider = url.searchParams.get("provider");
        const state = url.searchParams.get("state");
        const rows = [...server.triggers.values()].filter(
          (row) =>
            (!flowId || row.flow_id === flowId) &&
            (!provider || row.provider === provider) &&
            (!state || row.state === state),
        );
        rows.forEach(settleSubscription);
        const operator = url.searchParams.get("scope") === "all";
        await route.fulfill({
          json: rows.map((row) => {
            const body = read(row);
            if (!operator) delete (body as Partial<typeof body>).owner_username;
            return body;
          }),
        });
        return;
      }

      if (segments[0] === "bulk" && method === "POST") {
        const action = segments[1] as "pause" | "resume";
        const body = request.postDataJSON() as {
          provider?: string;
          trigger_ids?: string[];
          dry_run?: boolean;
        };
        server.bulkBodies.push(body);
        const matched = [...server.triggers.values()].filter(
          (row) =>
            (!body.provider || row.provider === body.provider) &&
            (!body.trigger_ids || body.trigger_ids.includes(row.id)),
        );
        // `_pausable` / `_resumable` in services/triggers/operator.py: resume
        // only undoes an admin pause, never an owner's.
        const changed = matched.filter((row) =>
          action === "pause"
            ? ARMED_STATES.has(row.state)
            : row.state === "paused" && row.admin_paused_at !== null,
        );
        if (!body.dry_run) {
          for (const row of changed) {
            row.state = action === "pause" ? "paused" : "active";
            row.admin_paused_at = action === "pause" ? stamp() : null;
            row.updated_at = stamp();
          }
        }
        await route.fulfill({
          json: {
            action,
            dry_run: Boolean(body.dry_run),
            matched: matched.length,
            changed: changed.map((row) => row.id),
            unchanged: matched
              .filter((row) => !changed.includes(row))
              .map((row) => row.id),
            failed: [],
            owners: new Set(matched.map((row) => row.user_id)).size,
          },
        });
        return;
      }

      const row = server.triggers.get(decodeURIComponent(segments[0]));
      if (!row) {
        await route.fulfill({
          status: 404,
          json: { detail: "Trigger not found" },
        });
        return;
      }
      const sub = segments[1];

      if (!sub && method === "GET") {
        settleSubscription(row);
        const body = read(row);
        // The single-trigger route has no list-only fields.
        delete (body as Partial<typeof body>).flow_name;
        delete (body as Partial<typeof body>).owner_username;
        await route.fulfill({ json: body });
        return;
      }
      if (!sub && method === "DELETE") {
        server.triggers.delete(row.id);
        await route.fulfill({ status: 204, body: "" });
        return;
      }
      if (sub === "enable" && method === "POST") {
        const connection = row.connection_id
          ? server.connections.get(row.connection_id)
          : undefined;
        if (connection && !connection.allow_non_interactive) {
          row.state = "needs_reconnect";
          row.last_error = CONNECTION_NOT_AUTHORIZED_ERROR;
        } else if (row.provider && (options.subscribePolls ?? 0) > 0) {
          row.state = "pending";
          row.last_error = null;
          subscribing.set(row.id, options.subscribePolls ?? 0);
        } else {
          row.state = "active";
          row.last_error = null;
          row.next_fire_at =
            row.kind === "schedule" ? "2026-10-17T09:00:00Z" : null;
        }
        row.admin_paused_at = null;
        row.updated_at = stamp();
        await route.fulfill({ json: read(row) });
        return;
      }
      if (sub === "disable" && method === "POST") {
        row.state = "paused";
        subscribing.delete(row.id);
        row.updated_at = stamp();
        await route.fulfill({ json: read(row) });
        return;
      }
      if (sub === "test" && method === "POST") {
        const event = addEvent(row, {
          dedupe_key: `test:${row.id}:${sequence + 1}`,
          payload: { test: true, source: row.kind },
        });
        await route.fulfill({ json: event });
        return;
      }
      if (sub === "events" && method === "GET") {
        const limit = Number(url.searchParams.get("limit") ?? 50);
        const offset = Number(url.searchParams.get("offset") ?? 0);
        await route.fulfill({
          json: server.events
            .filter((event) => event.trigger_id === row.id)
            .slice(offset, offset + limit),
        });
        return;
      }
      if (sub === "replay" && method === "POST") {
        const { event_id } = request.postDataJSON() as { event_id: string };
        const original = server.events.find((event) => event.id === event_id);
        if (!original) {
          await route.fulfill({
            status: 404,
            json: { detail: "Event not found" },
          });
          return;
        }
        const event = addEvent(row, {
          payload: original.payload,
          replay_of_event_id: original.id,
          dedupe_key: `replay:${original.id}:${sequence + 1}`,
        });
        await route.fulfill({ json: event });
        return;
      }
      if (sub === "ingress" && method === "GET") {
        await route.fulfill({ json: ingressOf(row, secrets.has(row.id)) });
        return;
      }
      if (sub === "signing-secret" && method === "POST") {
        secrets.add(row.id);
        await route.fulfill({
          json: {
            ...ingressOf(row, true),
            signing_secret: MOCK_SIGNING_SECRET,
          },
        });
        return;
      }
      await route.fulfill({
        status: 405,
        json: { detail: "Method not allowed" },
      });
    },
  );

  return server;
}

function ingressOf(row: MockTrigger, hasSecret: boolean) {
  const publicId = `pub-${row.id}`;
  return {
    trigger_id: row.id,
    public_id: hasSecret ? publicId : null,
    ingress_url: hasSecret
      ? `http://localhost:7860/api/v1/triggers/ingress/${publicId}`
      : null,
    has_signing_secret: hasSecret,
  };
}

export { MOCK_SIGNING_SECRET };
