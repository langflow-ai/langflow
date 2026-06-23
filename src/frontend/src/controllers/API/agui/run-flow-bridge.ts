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
import {
  findLastBotMessage,
  updateMessageProperties,
} from "@/components/core/playgroundComponent/chat-view/utils/message-utils";
import { BuildStatus } from "@/constants/enums";
import { persistMessageProperties } from "@/controllers/API/helpers/persist-message-properties";
import { getFetchCredentials } from "@/customization/utils/get-fetch-credentials";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useHitlStore } from "@/stores/hitlStore";
import { useMessagesStore } from "@/stores/messagesStore";
import type {
  LogsLogType,
  VertexBuildTypeAPI,
  VertexDataTypeAPI,
} from "@/types/api";
import type { ChatInputType, ChatOutputType } from "@/types/chat";
import { api } from "../api";
import { injectHumanInputCard } from "./human-input-card";
import {
  buildWorkflowRunRequest,
  createWorkflowAgent,
  WORKFLOWS_ENDPOINT,
  WORKFLOWS_PUBLIC_ENDPOINT,
  type WorkflowRunOptions,
} from "./run-agent";

const AGUI_STATUS_TO_BUILD_STATUS: Record<string, BuildStatus> = {
  pending: BuildStatus.TO_BUILD,
  running: BuildStatus.BUILDING,
  success: BuildStatus.BUILT,
  error: BuildStatus.ERROR,
  // A branch component's not-taken vertices arrive as ``inactive`` so the
  // canvas can render them as skipped instead of leaving them on ``pending``.
  inactive: BuildStatus.INACTIVE,
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

type FlowBuildStatusEntry = {
  status: BuildStatus;
  timestamp?: string;
};

/**
 * Hooks the bridge exposes to {@link handleAGUIEvent}. Injecting them keeps
 * the event-dispatch logic testable without importing the real flow / alert
 * stores or the chat-view message handler.
 */
export interface BridgeContext {
  setRunId: (runId: string) => void;
  applyDelta: (ops: JsonPatchOp[]) => void;
  handleCustomEvent: (eventType: string, data: unknown) => void;
  onHumanInput: (payload: unknown) => void;
  handleEndEvent: (data: unknown) => void;
  handleLogEvent: (data: unknown) => void;
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
      if (custom.value.event_type === "end") {
        ctx.handleEndEvent(custom.value.data);
      } else {
        ctx.handleCustomEvent(custom.value.event_type, custom.value.data);
      }
    } else if (custom.name === "langflow.human_input_required") {
      // Non-terminal: surface the card; the SSE ends at suspend and reattaches on resume.
      ctx.onHumanInput(custom.value);
    } else if (custom.name === "langflow.log") {
      ctx.handleLogEvent(custom.value);
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
  runningNodeIds?: Set<string>,
  originalBuildStatuses?: Map<string, FlowBuildStatusEntry | undefined>,
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
    if (originalBuildStatuses && !originalBuildStatuses.has(nodeId)) {
      const currentStatus = useFlowStore.getState().flowBuildStatus[nodeId];
      originalBuildStatuses.set(
        nodeId,
        currentStatus ? { ...currentStatus } : undefined,
      );
    }
    flowStore.updateBuildStatus([nodeId], buildStatus);
    nodeIds.add(nodeId);

    // Drive the canvas edge animation in step with build status so the AG-UI
    // path matches the v1 build callbacks: edges from a node light up while
    // it runs and stop when it finishes (either way). Without this only the
    // bridge's final ``finish()`` clears edges, and they never animate during
    // the run.
    if (value.status === "running") {
      if (runningNodeIds) {
        runningNodeIds.add(nodeId);
        flowStore.clearAndSetEdgesRunning([...runningNodeIds]);
      } else {
        flowStore.updateEdgesRunningByNodes([nodeId], true);
      }
    } else if (
      value.status === "success" ||
      value.status === "error" ||
      value.status === "inactive"
    ) {
      if (runningNodeIds) {
        runningNodeIds.delete(nodeId);
        flowStore.clearAndSetEdgesRunning([...runningNodeIds]);
      } else {
        flowStore.updateEdgesRunningByNodes([nodeId], false);
      }
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
  const runningNodeIds = new Set<string>();
  const originalBuildStatuses = new Map<
    string,
    FlowBuildStatusEntry | undefined
  >();
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
  let markRunningAsError = false;

  const persistBuildDuration = (data: unknown) => {
    const buildDuration = (data as { build_duration?: number } | null)
      ?.build_duration;
    if (buildDuration == null) return;

    const durationMs = buildDuration * 1000;
    const currentFlowStore = useFlowStore.getState();
    currentFlowStore.setBuildDuration(durationMs);

    const found = findLastBotMessage(
      currentFlowStore.buildingFlowId ?? undefined,
      currentFlowStore.buildingSessionId ?? undefined,
    );
    if (!found) return;
    if (found.message.properties?.build_duration != null) return;

    useMessagesStore.getState().updateMessagePartial({
      id: found.message.id,
      properties: {
        ...found.message.properties,
        build_duration: durationMs,
      },
    });

    updateMessageProperties(found.message.id!, found.queryKey, {
      build_duration: durationMs,
    });
    persistMessageProperties(found.message.id!, {
      ...found.message,
      properties: {
        ...found.message.properties,
        build_duration: durationMs,
      },
    });
  };

  const appendLogEvent = (data: unknown) => {
    const {
      component_id,
      output,
      name,
      message,
      type: logType,
    } = (data ?? {}) as {
      component_id?: string;
      output?: string;
    } & Partial<LogsLogType>;
    if (!component_id || !output) {
      console.error(
        "[runFlowAGUI] Received malformed log event; missing component_id or output",
        data,
      );
      return;
    }
    useFlowStore.getState().appendLogToFlowPool(component_id, output, {
      name,
      message,
      type: logType,
    } as LogsLogType);
  };

  const markRunningNodesFailed = () => {
    const current = useFlowStore.getState();
    const flowBuildStatus = { ...current.flowBuildStatus };
    for (const nodeId of touchedNodeIds) {
      if (flowBuildStatus[nodeId]?.status === BuildStatus.BUILDING) {
        flowBuildStatus[nodeId] = {
          ...flowBuildStatus[nodeId],
          status: BuildStatus.ERROR,
        };
      }
    }
    useFlowStore.setState({ flowBuildStatus });
  };

  const restoreOriginalBuildStatuses = () => {
    const current = useFlowStore.getState();
    const flowBuildStatus = { ...current.flowBuildStatus };
    for (const [nodeId, status] of originalBuildStatuses) {
      if (flowBuildStatus[nodeId]?.status !== BuildStatus.BUILDING) continue;
      if (status) {
        flowBuildStatus[nodeId] = { ...status };
      } else {
        delete flowBuildStatus[nodeId];
      }
    }
    useFlowStore.setState({ flowBuildStatus });
  };

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
    applyDelta: (ops) =>
      applyStateDelta(
        ops,
        runId,
        touchedNodeIds,
        runningNodeIds,
        originalBuildStatuses,
      ),
    handleCustomEvent: (eventType, data) => handleMessageEvent(eventType, data),
    onHumanInput: () => {
      // Stream mode can't durably suspend; HITL runs go through the background
      // path (runFlowHITL). Mark awaiting-input so the UI reflects the pause.
      flowStore.setAwaitingInput(true);
    },
    handleEndEvent: persistBuildDuration,
    handleLogEvent: appendLogEvent,
    onFinished: () => {
      terminalEventSeen = true;
      if (!opts.silent) {
        flowStore.setBuildInfo({ success: true });
      }
    },
    onError: (message) => {
      terminalEventSeen = true;
      markRunningAsError = true;
      flowStore.setBuildInfo({ error: [message], success: false });
      setErrorData({ title: "Workflow run failed", list: [message] });
    },
  };

  return new Promise<void>((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      flowStore.clearAndSetEdgesRunning([]);
      flowStore.setIsBuilding(false);
      if (markRunningAsError) {
        markRunningNodesFailed();
      } else if (!terminalEventSeen) {
        restoreOriginalBuildStatuses();
      } else {
        flowStore.revertBuiltStatusFromBuilding();
      }
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
        markRunningAsError = true;
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
          markRunningAsError = true;
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

/** Background-run body (mode="background"); HITL needs the durable substrate. */
function buildBackgroundRunRequest(opts: WorkflowRunOptions) {
  const body: Record<string, unknown> = {
    flow_id: opts.flowId,
    input_value: opts.message ?? "",
    mode: "background",
    stream_protocol: "agui",
  };
  if (opts.threadId) body.session_id = opts.threadId;
  if (opts.tweaks) body.tweaks = opts.tweaks;
  if (opts.startComponentId) body.start_component_id = opts.startComponentId;
  if (opts.stopComponentId) body.stop_component_id = opts.stopComponentId;
  if (opts.flowData) body.data = opts.flowData;
  if (opts.files && opts.files.length > 0) body.files = opts.files;
  return body;
}

/**
 * Consume a background run's durable event stream (`GET /{job_id}/events`) and fold
 * events into the flow store. Resolves when the run ends, suspends for human input,
 * or the request errors. Reused for the initial run and for resume reattach.
 *
 * Uses a direct fetch + SSE parser rather than the AG-UI ``HttpAgent``: a paused run
 * closes the stream WITHOUT a terminal ``RUN_FINISHED``, which the agent's protocol
 * verifier treats as a violation and can swallow the pause event we depend on.
 */
export async function consumeBackgroundEvents(
  jobId: string,
  opts: WorkflowRunOptions & { signal?: AbortSignal },
  lastEventId?: string,
  { skipCardInjection = false }: { skipCardInjection?: boolean } = {},
): Promise<void> {
  const flowStore = useFlowStore.getState();
  const setErrorData = useAlertStore.getState().setErrorData;
  const touchedNodeIds = new Set<string>();
  let runId = jobId;
  let suspended = false;
  let terminalSeen = false;

  const ctx: BridgeContext = {
    setRunId: (r) => {
      runId = r;
    },
    applyDelta: (ops) => applyStateDelta(ops, runId, touchedNodeIds),
    handleCustomEvent: (eventType, data) => handleMessageEvent(eventType, data),
    // The background replay routes 'end' through the same message handler (as before the
    // end/log split); logs aren't surfaced separately on the reattach path.
    handleEndEvent: (data) => handleMessageEvent("end", data),
    handleLogEvent: () => {},
    onHumanInput: (payload) => {
      // After a resume the pause is already answered; the replay re-emits it, but
      // re-injecting would re-show the card/badge. Stream the continued run only.
      if (skipCardInjection) return;
      suspended = true;
      injectHumanInputCard(payload as Record<string, unknown>, jobId, opts);
    },
    onFinished: () => {
      // A HITL resume continuation is not a user-initiated build, so the caller can pass
      // silent to suppress the "Flow built successfully" toast on the canvas.
      if (!opts.silent) flowStore.setBuildInfo({ success: true });
    },
    onError: (message) => {
      flowStore.setBuildInfo({ error: [message], success: false });
      setErrorData({ title: "Workflow run failed", list: [message] });
    },
  };

  const finish = () => {
    flowStore.updateEdgesRunningByNodes([...touchedNodeIds], false);
    // The spinner reads isBuilding, so it clears whether the run parked or ended.
    flowStore.setIsBuilding(false);
    // Only a definitive terminal (RUN_FINISHED/RUN_ERROR) or an observed pause may change the
    // awaiting/badge state. A stream that ends having seen NEITHER — e.g. a reattach whose replay
    // started past the pause, or the live tail that never gets the pause frame — must leave the
    // parked state intact; clearing on mere absence drops the badge of a still-SUSPENDED run.
    if (suspended) {
      flowStore.setAwaitingInput(true);
    } else if (terminalSeen) {
      flowStore.setAwaitingInput(false);
      useHitlStore.getState().clear();
    }
    flowStore.revertBuiltStatusFromBuilding();
  };

  const headers: Record<string, string> = { Accept: "text/event-stream" };
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;
  const url = `${WORKFLOWS_ENDPOINT}/${encodeURIComponent(jobId)}/events`;

  try {
    const response = await fetch(url, {
      method: "GET",
      headers,
      credentials: getFetchCredentials(),
      signal: opts.signal,
    });
    if (!response.ok || !response.body) {
      ctx.onError(`Events stream failed with status ${response.status}`);
      finish();
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let terminal = false;

    const dispatch = (frame: string): boolean => {
      const dataLine = frame
        .split("\n")
        .find((line) => line.startsWith("data:"));
      if (!dataLine) return false;
      let event: BaseEvent;
      try {
        event = JSON.parse(dataLine.slice(5).trim()) as BaseEvent;
      } catch {
        return false;
      }
      if (handleAGUIEvent(event, ctx)) {
        // A terminal event supersedes a replayed pause (resume reattach re-emits it).
        suspended = false;
        terminalSeen = true;
        return true;
      }
      return false;
    };

    while (!terminal) {
      const { value, done } = await reader.read();
      if (done) {
        // The stream can close right after the pause event without a trailing
        // blank line; flush whatever is buffered so that last frame isn't lost.
        if (buffer.trim()) dispatch(buffer);
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
        if (dispatch(frame)) {
          terminal = true;
          break;
        }
      }
    }
    finish();
  } catch (err) {
    if ((err as Error)?.name !== "AbortError") {
      ctx.onError((err as Error)?.message ?? "Events stream error");
    }
    finish();
  }
}

/**
 * Run a flow that contains a Human Input node through the durable background path:
 * submit in background mode, then consume the run's event stream. The pause renders
 * an interactive card; resume reattaches via {@link consumeBackgroundEvents}.
 */
export async function runFlowHITL(
  opts: WorkflowRunOptions & { signal?: AbortSignal },
): Promise<void> {
  const body = buildBackgroundRunRequest(opts);
  const { data } = await api.post(WORKFLOWS_ENDPOINT, body);
  const jobId: string | undefined = data?.job_id;
  if (!jobId) {
    useFlowStore.getState().setBuildInfo({
      error: ["Background run did not return a job id"],
      success: false,
    });
    useFlowStore.getState().setIsBuilding(false);
    return;
  }
  await consumeBackgroundEvents(jobId, opts);
}
