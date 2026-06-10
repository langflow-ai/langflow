/**
 * Bridge: run a workflow through the AG-UI service and update flowStore.
 *
 * ``flowStore.buildFlow`` calls this function to drive a run through the
 * v2 workflows endpoint. It starts the AG-UI HttpAgent and folds each
 * event into the existing flow-store methods (``updateBuildStatus``,
 * ``addDataToFlowPool``, ``setBuildInfo``, ``setIsBuilding``) so the
 * canvas and "built successfully" toast keep working.
 */

import { type BaseEvent, EventType } from "@ag-ui/client";
import { handleMessageEvent } from "@/components/core/playgroundComponent/chat-view/utils/message-event-handler";
import { BuildStatus } from "@/constants/enums";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import type {
  ChatInputType,
  ChatOutputType,
  VertexBuildTypeAPI,
  VertexDataTypeAPI,
} from "@/types/api";
import {
  buildWorkflowRunRequest,
  createWorkflowAgent,
  WORKFLOWS_PUBLIC_ENDPOINT,
  type WorkflowRunOptions,
} from "./run-agent";

const AGUI_STATUS_TO_BUILD_STATUS: Record<string, BuildStatus> = {
  pending: BuildStatus.TO_BUILD,
  running: BuildStatus.BUILDING,
  success: BuildStatus.BUILT,
  error: BuildStatus.ERROR,
};

interface JsonPatchOp {
  op: string;
  path: string;
  value?: unknown;
}

interface AGUINodeState {
  status: string;
  output: VertexDataTypeAPI | null;
}

/**
 * Hooks the bridge exposes to {@link handleAGUIEvent}. Injecting them keeps
 * the event-dispatch logic testable without importing the real flow / alert
 * stores or the chat-view message handler.
 */
export interface BridgeContext {
  setRunId: (runId: string) => void;
  applyDelta: (ops: JsonPatchOp[]) => void;
  handleCustomEvent: (eventType: string, data: unknown) => void;
  onFinished: () => void;
  onError: (message: string) => void;
}

/**
 * Dispatch a single AG-UI event into the bridge context.
 *
 * Returns ``true`` when the event is terminal (``RUN_FINISHED`` or
 * ``RUN_ERROR``); the caller must then tear down the subscription and
 * resolve the run. Pulling this out of the inline subscribe handler keeps
 * the terminal-event contract unit-testable.
 */
export function handleAGUIEvent(event: BaseEvent, ctx: BridgeContext): boolean {
  if (event.type === EventType.RUN_STARTED) {
    const started = event as unknown as { runId?: string };
    if (started.runId) ctx.setRunId(started.runId);
    return false;
  }
  if (event.type === EventType.STATE_DELTA) {
    const ops = (event as unknown as { delta?: JsonPatchOp[] }).delta ?? [];
    ctx.applyDelta(ops);
    return false;
  }
  if (event.type === EventType.CUSTOM) {
    const custom = event as unknown as {
      name?: string;
      value?: { event_type?: string; data?: unknown };
    };
    if (custom.name === "langflow.event" && custom.value?.event_type) {
      ctx.handleCustomEvent(custom.value.event_type, custom.value.data);
    }
    return false;
  }
  if (event.type === EventType.RUN_FINISHED) {
    ctx.onFinished();
    return true;
  }
  if (event.type === EventType.RUN_ERROR) {
    const message =
      (event as unknown as { message?: string }).message ?? "Unknown run error";
    ctx.onError(message);
    return true;
  }
  return false;
}

/**
 * @internal
 *
 * Exported only so the JSON-Patch parsing + status fallback can be pinned
 * directly. `runFlowAGUI` is the sole production caller; tests live in
 * `__tests__/apply-state-delta.test.ts`. The JSDoc `@internal` tag is what
 * TypeScript's `--stripInternal` recognizes, so this stays out of generated
 * `.d.ts` if the project ever turns that flag on.
 */
export function applyStateDelta(
  ops: JsonPatchOp[],
  runId: string,
  nodeIds: Set<string>,
): void {
  const flowStore = useFlowStore.getState();
  for (const op of ops) {
    const match = /^\/nodes\/([^/]+)$/.exec(op.path);
    if (!match) continue;
    if (op.op !== "add" && op.op !== "replace") continue;
    const nodeId = match[1];
    const value = op.value as AGUINodeState | undefined;
    if (!value || typeof value !== "object") continue;

    const buildStatus =
      AGUI_STATUS_TO_BUILD_STATUS[value.status] ?? BuildStatus.BUILDING;
    flowStore.updateBuildStatus([nodeId], buildStatus);
    nodeIds.add(nodeId);

    // Drive the canvas edge animation in step with build status so the AG-UI
    // path matches the v1 build callbacks: edges from a node light up while
    // it runs and stop when it finishes (either way). Without this only the
    // bridge's final ``finish()`` clears edges, and they never animate during
    // the run.
    if (value.status === "running") {
      flowStore.updateEdgesRunningByNodes([nodeId], true);
    } else if (value.status === "success" || value.status === "error") {
      flowStore.updateEdgesRunningByNodes([nodeId], false);
    }

    // Only the final per-vertex emission carries the result data; running
    // states have ``output: null`` and contribute no flow-pool entry.
    if (value.output) {
      const entry: VertexBuildTypeAPI = {
        id: nodeId,
        inactivated_vertices: null,
        next_vertices_ids: [],
        top_level_vertices: [],
        run_id: runId,
        valid: value.status === "success",
        data: value.output,
        timestamp: new Date().toISOString(),
        params: null,
        messages: [] as ChatOutputType[] | ChatInputType[],
        artifacts: null,
      };
      flowStore.addDataToFlowPool(entry, nodeId);
    }
  }
}

/**
 * Run a workflow through the AG-UI service and update flowStore as events
 * arrive. Resolves when the run ends (RUN_FINISHED or RUN_ERROR), the
 * underlying observable errors, or ``signal`` aborts.
 *
 * Passing the caller's ``AbortSignal`` (typically
 * ``flowStore.buildController.signal``) lets ``flowStore.stopBuilding`` cancel
 * the in-flight SSE request, not just the local build state. Without it the
 * agent's internal AbortController would keep streaming after Stop.
 */
export async function runFlowAGUI(
  opts: WorkflowRunOptions & { signal?: AbortSignal },
): Promise<void> {
  // The shareable-playground popup posts on behalf of a visitor that
  // does not own the flow. Route those runs to the public endpoint so
  // the backend applies the public-access mitigations (virtual_flow_id,
  // session namespacing, file-path validation, owner impersonation).
  // The canvas's regular runs keep going to ``/api/v2/workflows``.
  const usePublicEndpoint =
    opts.usePublicEndpoint ?? useFlowStore.getState().playgroundPage;
  const body = buildWorkflowRunRequest({ ...opts, usePublicEndpoint });
  const agent = createWorkflowAgent({
    body,
    url: usePublicEndpoint ? WORKFLOWS_PUBLIC_ENDPOINT : undefined,
  });
  // Replace the agent's internal AbortController with one tied to the
  // caller's signal so an upstream stop also aborts the SSE fetch. Without
  // this, the agent owns its own controller and the stream keeps running
  // even after ``stopBuilding`` aborts the caller's controller.
  if (opts.signal) {
    const linkedController = new AbortController();
    if (opts.signal.aborted) {
      linkedController.abort();
    } else {
      opts.signal.addEventListener("abort", () => linkedController.abort(), {
        once: true,
      });
    }
    (agent as { abortController: AbortController }).abortController =
      linkedController;
  }
  const flowStore = useFlowStore.getState();
  const setErrorData = useAlertStore.getState().setErrorData;
  const touchedNodeIds = new Set<string>();
  // Server derives run_id from session_id/flow_id and announces it via
  // RUN_STARTED. Until that arrives we have no id to stamp on flow-pool
  // entries, so we fall back to an empty string (matches the legacy
  // contract for an unresolved run).
  let runId = "";
  // ``buildInfo`` must be set on every terminal path (RUN_FINISHED,
  // RUN_ERROR, observable error, complete-without-terminal-event, abort)
  // so the caller's analytics ``trackFlowBuild`` can read success vs
  // failure. Without this, a silent ``complete:`` would leave ``buildInfo``
  // ``null`` and ``trackFlowBuild`` would mis-record the run as success.
  let terminalEventSeen = false;

  // `agent.run` still needs a `RunAgentInput` for the client-side apply
  // pipeline (subscriber correlation); the actual wire body is the native
  // `WorkflowRunRequest` set on the agent. These ids stay local.
  const runInput = {
    threadId: opts.threadId ?? "",
    runId: "",
    state: {},
    messages: [],
    tools: [],
    context: [],
    forwardedProps: {},
  };

  // Side-channel: the backend mirrors message-shaped events (add_message,
  // token, remove_message, error) as a `langflow.event` CustomEvent so
  // the playground's chat-view utilities can consume them in their v1
  // shape. A follow-up can retire this once chat-view consumes the
  // AG-UI `TEXT_MESSAGE_*` lifecycle directly.
  const ctx: BridgeContext = {
    setRunId: (r) => {
      runId = r;
    },
    applyDelta: (ops) => applyStateDelta(ops, runId, touchedNodeIds),
    handleCustomEvent: (eventType, data) => handleMessageEvent(eventType, data),
    onFinished: () => {
      terminalEventSeen = true;
      flowStore.setBuildInfo({ success: true });
    },
    onError: (message) => {
      terminalEventSeen = true;
      flowStore.setBuildInfo({ error: [message], success: false });
      setErrorData({ title: "Workflow run failed", list: [message] });
    },
  };

  return new Promise<void>((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      flowStore.updateEdgesRunningByNodes([...touchedNodeIds], false);
      flowStore.setIsBuilding(false);
      flowStore.revertBuiltStatusFromBuilding();
      resolve();
    };

    const abortHandler = () => {
      // ``buildController.abort`` was called from ``flowStore.stopBuilding``.
      // Mark the run as a failure so analytics records the cancellation and
      // tear the subscription down (the agent's internal AbortController is
      // already linked to this signal, so the SSE fetch is already aborting).
      // Do NOT write an ``error`` string here: ``stopBuilding`` already
      // surfaces the user-facing "Build stopped" alert. A second message in
      // ``buildInfo.error`` would render the same text inside the canvas
      // footer and trip strict locators ("build stopped" resolved twice).
      if (!terminalEventSeen) {
        flowStore.setBuildInfo({ success: false });
      }
      subscription.unsubscribe();
      finish();
    };
    if (opts.signal) {
      if (opts.signal.aborted) {
        // Already aborted before we even started. Skip the subscribe.
        flowStore.setBuildInfo({ success: false });
        finish();
        return;
      }
      opts.signal.addEventListener("abort", abortHandler, { once: true });
    }

    const subscription = agent.run(runInput).subscribe({
      next: (event: BaseEvent) => {
        if (handleAGUIEvent(event, ctx)) {
          // Tear the subscription down on the terminal event instead of
          // waiting for `complete:` from the SSE stream. A server-side
          // keepalive or buffered chunk after the terminal event can leave
          // the observable open, which would leave the canvas stuck on
          // ``isBuilding=true`` indefinitely.
          subscription.unsubscribe();
          finish();
        }
      },
      error: (err: Error) => {
        flowStore.setBuildInfo({ error: [err.message], success: false });
        setErrorData({ title: "Workflow run failed", list: [err.message] });
        subscription.unsubscribe();
        finish();
      },
      complete: () => {
        // ``complete`` without a terminal event means the SSE stream closed
        // cleanly but never delivered RUN_FINISHED/RUN_ERROR (server crash,
        // truncated response, proxy timeout). Record an error so analytics
        // doesn't treat a silent close as success.
        if (!terminalEventSeen) {
          flowStore.setBuildInfo({
            error: ["Workflow run ended unexpectedly"],
            success: false,
          });
        }
        subscription.unsubscribe();
        finish();
      },
    });
  });
}
