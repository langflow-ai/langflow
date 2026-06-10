/**
 * v2 workflows run service.
 *
 * Builds the native `WorkflowRunRequest` body that
 * `POST /api/v2/workflows` accepts and runs it through a thin `HttpAgent`
 * subclass so the frontend keeps consuming the typed AG-UI event stream
 * (`stream_protocol: "agui"`) emitted by the server.
 *
 * The endpoint Pydantic model has `extra="forbid"`, so this builder must
 * never leak AG-UI `RunAgentInput` keys (`threadId`, `runId`,
 * `forwardedProps`, `state`, `messages`, `tools`, `context`) onto the wire.
 */

import {
  HttpAgent,
  type HttpAgentConfig,
  type RunAgentInput,
} from "@ag-ui/client";

/** Execution mode accepted by the v2 workflows endpoint. */
export type WorkflowMode = "sync" | "stream" | "background";

/** Streaming protocol selector (server-side adapter registry). */
export type StreamProtocol = "agui" | "langflow";

/** Options describing one Langflow workflow run. */
export interface WorkflowRunOptions {
  /** The Langflow flow id to run. Required by the v2 endpoint. */
  flowId: string;
  /** User chat input (last user message) — maps to `input_value`. */
  message?: string;
  /** Component-keyed parameter overrides, e.g. `{ChatInput-abc: {input_value: "..."}}`. */
  tweaks?: Record<string, Record<string, unknown>>;
  /** Execution mode; defaults to `stream`. */
  mode?: WorkflowMode;
  /** Chat-session id — maps to the endpoint's `session_id`. Server derives `run_id`/`thread_id`. */
  threadId?: string;
  /** Optional partial-run start vertex id. */
  startComponentId?: string;
  /** Optional partial-run stop vertex id. */
  stopComponentId?: string;
  /** Current flow data (nodes + edges) to run; falls back to the DB copy if omitted. */
  flowData?: { nodes: unknown[]; edges: unknown[] };
  /** Runtime file references the graph build needs (e.g. uploaded file paths). */
  files?: string[];
  /**
   * When true, route the request to the public-flow endpoint
   * (``/api/v2/workflows/public``) instead of the authenticated one.
   *
   * Set by the shareable-playground popup so the backend can apply the
   * public-access mitigations (per-visitor virtual_flow_id, session
   * namespacing, file-path validation, owner impersonation) that mirror
   * v1's ``build_public_tmp``.
   *
   * When enabled the request body is narrowed too: ``tweaks`` and
   * ``flowData`` are silently dropped because the public schema forbids
   * them (visitors must never override the stored flow definition).
   */
  usePublicEndpoint?: boolean;
}

/** The v2 workflows endpoint path. */
export const WORKFLOWS_ENDPOINT = "/api/v2/workflows";

/** The v2 public workflows endpoint path (shareable playground). */
export const WORKFLOWS_PUBLIC_ENDPOINT = "/api/v2/workflows/public";

/**
 * Wire shape for `POST /api/v2/workflows`. Mirrors
 * `lfx.schema.workflow.WorkflowRunRequest`; the Pydantic model rejects
 * extra fields, so this type intentionally has no escape hatch.
 */
export interface WorkflowRunRequestBody {
  flow_id: string;
  input_value: string;
  mode: WorkflowMode;
  stream_protocol: StreamProtocol;
  tweaks?: Record<string, Record<string, unknown>>;
  session_id?: string;
  data?: { nodes: unknown[]; edges: unknown[] };
  files?: string[];
  start_component_id?: string;
  stop_component_id?: string;
}

/**
 * Build a native `WorkflowRunRequest` body for the v2 workflows endpoint.
 *
 * The frontend pins `stream_protocol: "agui"` so the SSE response is a
 * typed AG-UI event stream the existing consumers already understand.
 * `run_id` and `thread_id` are derived server-side from `session_id` and
 * `flow_id`; we only forward `session_id` when the caller actually has one.
 */
export function buildWorkflowRunRequest(
  opts: WorkflowRunOptions,
): WorkflowRunRequestBody {
  const mode = opts.mode ?? "stream";
  // ``createWorkflowAgent`` always patches ``Accept: text/event-stream`` and
  // ``HttpAgent.run`` decodes the response as SSE. ``mode=sync`` returns
  // ``application/json`` and ``mode=background`` returns a job JSON, so
  // either of those modes through this builder would mis-decode at runtime.
  // The only in-tree caller (``runFlowAGUI``) sends ``stream``; this guard
  // catches accidental misuse early instead of silently producing a broken
  // run. Sync / background callers should go through a JSON fetch path.
  if (mode !== "stream") {
    throw new Error(
      `createWorkflowAgent only supports mode="stream"; got "${mode}". ` +
        `Use a JSON fetch against ${WORKFLOWS_ENDPOINT} for sync / background.`,
    );
  }
  const body: WorkflowRunRequestBody = {
    flow_id: opts.flowId,
    input_value: opts.message ?? "",
    mode,
    stream_protocol: "agui",
  };
  if (opts.threadId) body.session_id = opts.threadId;
  // The public endpoint's schema (extra="forbid") rejects tweaks/data:
  // visitors must never override the stored flow definition. Drop them
  // here instead of letting the request fail with a 422.
  const isPublic = !!opts.usePublicEndpoint;
  if (!isPublic && opts.tweaks) body.tweaks = opts.tweaks;
  if (opts.startComponentId) body.start_component_id = opts.startComponentId;
  if (opts.stopComponentId) body.stop_component_id = opts.stopComponentId;
  if (!isPublic && opts.flowData) body.data = opts.flowData;
  if (opts.files && opts.files.length > 0) body.files = opts.files;
  return body;
}

/** Construction options for the workflow agent. */
export interface WorkflowAgentOptions {
  /** Native body to POST. Built via `buildWorkflowRunRequest`. */
  body: WorkflowRunRequestBody;
  /** Override the endpoint URL (defaults to `/api/v2/workflows`). */
  url?: string;
  /** Extra headers; cookies and `fetch-intercept`'d headers are sent automatically. */
  headers?: Record<string, string>;
}

/**
 * `HttpAgent` instance with `requestInit` swapped to POST a native
 * `WorkflowRunRequest` body instead of the AG-UI `RunAgentInput`.
 *
 * `HttpAgent` exposes `requestInit` as the documented override surface
 * ("Override this to customize the request"). We patch it on the instance
 * rather than subclassing because the project's ts-jest targets `es5`,
 * which can't extend the CJS-compiled class. Patching keeps us in sync
 * with future AG-UI updates (SSE framing, abort, headers) instead of
 * forking the whole client.
 */
export type WorkflowHttpAgent = HttpAgent & {
  workflowBody: WorkflowRunRequestBody;
};

/**
 * Create a workflow agent preconfigured for the v2 workflows endpoint.
 *
 * Auth is carried by the browser: same-origin cookies are sent automatically,
 * and Langflow's `fetch-intercept` registration adds any custom headers.
 */
export function createWorkflowAgent(
  opts: WorkflowAgentOptions,
): WorkflowHttpAgent {
  const config: HttpAgentConfig = {
    url: opts.url ?? WORKFLOWS_ENDPOINT,
    headers: opts.headers,
  };
  const agent = new HttpAgent(config) as WorkflowHttpAgent;
  agent.workflowBody = opts.body;
  // `requestInit` is the documented override surface on `HttpAgent`.
  // Swap it on the instance so the wire body is the native
  // `WorkflowRunRequest`; the AG-UI `RunAgentInput` passed to `run()`
  // is used only for client-side correlation.
  (
    agent as unknown as {
      requestInit: (input: RunAgentInput) => RequestInit;
    }
  ).requestInit = function requestInit(_input: RunAgentInput): RequestInit {
    return {
      method: "POST",
      headers: {
        ...agent.headers,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(agent.workflowBody),
      signal: agent.abortController.signal,
    };
  };
  return agent;
}
