import { BUILD_POLLING_INTERVAL } from "@/constants/constants";
import { BuildStatus, EventDeliveryType } from "@/constants/enums";
import { getFetchCredentials } from "@/customization/utils/get-fetch-credentials";
import useFlowStore from "@/stores/flowStore";
import { VertexLayerElementType } from "@/types/zustand/flow";
import { processEndVertexEvent } from "@/utils/buildUtils";

const BATCH_YIELD_MS = 50;

// Event types that can be processed synchronously (no await needed).
// These are batched together so React commits them in a single render.
const BATCHABLE_EVENTS = new Set(["end_vertex", "build_start", "build_end"]);

export async function customPollBuildEvents(
  url: string,
  buildResults: Array<boolean>,
  verticesStartTimeMs: Map<string, number>,
  callbacks: {
    onBuildStart?: (idList: VertexLayerElementType[]) => void;
    onBuildUpdate?: (data: any, status: BuildStatus, buildId: string) => void;
    onBuildComplete?: (allNodesValid: boolean) => void;
    onBuildError?: (
      title: string,
      list: string[],
      idList?: VertexLayerElementType[],
    ) => void;
    onGetOrderSuccess?: () => void;
    onValidateNodes?: (nodes: string[]) => void;
  },
  abortController: AbortController,
  onEvent,
): Promise<void> {
  let isDone = false;
  while (!isDone) {
    const response = await fetch(
      `${url}?event_delivery=${EventDeliveryType.POLLING}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/x-ndjson",
        },
        signal: abortController.signal,
        credentials: getFetchCredentials(),
      },
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail ||
          "Langflow was not able to connect to the server. Please make sure your connection is working properly.",
      );
    }

    const responseText = await response.text();

    if (!responseText.trim()) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      continue;
    }

    const eventLines = responseText.split("\n").filter((line) => line.trim());

    if (eventLines.length === 0) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      continue;
    }

    const events = eventLines.map((line) => JSON.parse(line));

    console.log(
      `[poll-batch] Received ${events.length} events:`,
      events.map((e) => e.event),
    );

    // Process events, batching consecutive batchable events (end_vertex,
    // build_start, build_end) so all their Zustand set() calls happen
    // synchronously — React 18 commits them in a single render.
    let i = 0;
    while (i < events.length) {
      const event = events[i];

      if (BATCHABLE_EVENTS.has(event.event)) {
        // Collect consecutive batchable events and process synchronously.
        // NO await in this loop — keeps everything in one synchronous
        // execution context for React batching.
        let batchCount = 0;
        let batchFailed = false;
        while (i < events.length && BATCHABLE_EVENTS.has(events[i].event)) {
          const ev = events[i];
          let result: boolean;

          if (ev.event === "end_vertex") {
            result = processEndVertexEvent(ev.data, buildResults, callbacks);
          } else if (ev.event === "build_start") {
            if (ev.data?.id) {
              useFlowStore
                .getState()
                .updateBuildStatus([ev.data.id], BuildStatus.BUILDING);
            }
            result = true;
          } else {
            // build_end
            if (ev.data?.id) {
              useFlowStore
                .getState()
                .updateBuildStatus([ev.data.id], BuildStatus.BUILT);
            }
            result = true;
          }

          if (!result) {
            batchFailed = true;
            isDone = true;
            abortController.abort();
            break;
          }
          batchCount++;
          i++;
        }

        console.log(
          `[poll-batch] Processed batch of ${batchCount} batchable events, yielding once`,
        );

        if (batchFailed) break;
        // Single yield for the entire batch
        await new Promise((resolve) => setTimeout(resolve, BATCH_YIELD_MS));
      } else {
        // Non-batchable events (vertices_sorted, end, error, add_message, token, etc.)
        console.log(
          `[poll-batch] Processing non-batchable event: ${event.event}`,
        );
        const result = await onEvent(
          event.event,
          event.data,
          buildResults,
          verticesStartTimeMs,
          callbacks,
        );
        if (!result) {
          isDone = true;
          abortController.abort();
          break;
        }
        if (event.event === "end") {
          isDone = true;
          break;
        }
        i++;
      }
    }

    await new Promise((resolve) => setTimeout(resolve, BUILD_POLLING_INTERVAL));
  }
}
