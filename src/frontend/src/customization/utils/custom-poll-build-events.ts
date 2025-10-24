import { BUILD_POLLING_INTERVAL } from "@/constants/constants";
import { BuildStatus, EventDeliveryType } from "@/constants/enums";
import { VertexLayerElementType } from "@/types/zustand/flow";

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
        signal: abortController.signal, // Add abort signal to fetch
      },
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail ||
          "Langflow was not able to connect to the server. Please make sure your connection is working properly.",
      );
    }

    // Get the response text - will be NDJSON format (one JSON per line)
    const responseText = await response.text();

    // Skip if empty response
    if (!responseText.trim()) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      continue;
    }

    // Split by newlines to get individual JSON objects
    const eventLines = responseText.split("\n").filter((line) => line.trim());

    // If no events, continue polling
    if (eventLines.length === 0) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      continue;
    }

    // Process all events in the NDJSON response
    for (const eventStr of eventLines) {
      // Process the event
      const event = JSON.parse(eventStr);
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

      // Check if this was the end event
      if (event.event === "end") {
        isDone = true;
        break;
      }
    }

    // Add a small delay between polls
    await new Promise((resolve) => setTimeout(resolve, BUILD_POLLING_INTERVAL));
  }
}
