import { BUILD_POLLING_INTERVAL } from "@/constants/constants";
import { BuildStatus, EventDeliveryType } from "@/constants/enums";
import { getFetchCredentials } from "@/customization/utils/get-fetch-credentials";
import { VertexLayerElementType } from "@/types/zustand/flow";
import { processBatchedEvents } from "@/utils/buildUtils";

export async function customPollBuildEvents(
  url: string,
  buildResults: Array<boolean>,
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

    const events: object[] = [];
    for (const line of eventLines) {
      try {
        events.push(JSON.parse(line));
      } catch (_e) {
        // Skip malformed JSON lines to avoid aborting the entire poll cycle
      }
    }

    if (events.length === 0) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      continue;
    }

    // Check if any event is the "end" event
    const hasEndEvent = events.some(
      (ev) => (ev as { event?: string }).event === "end",
    );

    const result = await processBatchedEvents(
      events,
      buildResults,
      callbacks,
      onEvent,
    );

    if (!result) {
      isDone = true;
      abortController.abort();
      break;
    }

    if (hasEndEvent) {
      isDone = true;
      break;
    }

    await new Promise((resolve) => setTimeout(resolve, BUILD_POLLING_INTERVAL));
  }
}
