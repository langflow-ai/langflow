import { useEffect, useRef } from "react";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowPoolType } from "@/types/zustand/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

const MAX_ERROR_DISPLAY_COUNT = 1;

interface PollingItem {
  interval: NodeJS.Timeout;
  timestamp: number;
  flowId: string;
  callback: () => Promise<void>;
}

const PollingManager = {
  pollingQueue: new Map<string, PollingItem[]>(),
  activePolls: new Map<string, PollingItem>(),

  enqueuePolling(flowId: string, pollingItem: PollingItem) {
    if (!this.pollingQueue.has(flowId)) {
      this.pollingQueue.set(flowId, []);
    }
    this.pollingQueue.set(
      flowId,
      (this.pollingQueue.get(flowId) || []).filter(
        (item) => item.timestamp !== pollingItem.timestamp,
      ),
    );
    this.pollingQueue.get(flowId)?.push(pollingItem);

    if (!this.activePolls.has(flowId)) {
      this.startNextPolling(flowId);
    }
  },

  startNextPolling(flowId: string) {
    const queue = this.pollingQueue.get(flowId) || [];
    if (queue.length === 0) {
      this.activePolls.delete(flowId);
      return;
    }

    const nextPoll = queue[0];
    this.activePolls.set(flowId, nextPoll);
    nextPoll.callback();
  },

  stopPoll(flowId: string) {
    const activePoll = this.activePolls.get(flowId);
    if (activePoll) {
      clearInterval(activePoll.interval);
      this.activePolls.delete(flowId);
      const queue = this.pollingQueue.get(flowId) || [];
      this.pollingQueue.set(
        flowId,
        queue.filter((item) => item.timestamp !== activePoll.timestamp),
      );
      this.startNextPolling(flowId);
    }
  },

  stopAll() {
    this.activePolls.forEach((poll) => clearInterval(poll.interval));
    this.activePolls.clear();
    this.pollingQueue.clear();
  },

  removeFromQueue(flowId: string, timestamp: number) {
    const queue = this.pollingQueue.get(flowId) || [];
    this.pollingQueue.set(
      flowId,
      queue.filter((item) => item.timestamp !== timestamp),
    );
  },
};

interface IGetBuilds {
  flowId: string;
  onSuccess?: (data: { vertex_builds: FlowPoolType }) => void;
  stopPollingOn?: (data: { vertex_builds: FlowPoolType }) => boolean;
}

export const useGetBuildsMutation: useMutationFunctionType<
  undefined,
  IGetBuilds
> = (options?) => {
  const { mutate } = UseRequestProcessor();
  const webhookPollingInterval = useUtilityStore(
    (state) => state.webhookPollingInterval,
  );

  const setFlowPool = useFlowStore((state) => state.setFlowPool);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  const flowIdRef = useRef<string | null>(null);
  const requestInProgressRef = useRef<Record<string, boolean>>({});
  const errorDisplayCountRef = useRef<number>(0);
  const timeoutIdsRef = useRef<number[]>([]);

  const setErrorData = useAlertStore((state) => state.setErrorData);

  const getBuildsFn = async (
    payload: IGetBuilds,
  ): Promise<{ vertex_builds: FlowPoolType } | undefined> => {
    if (requestInProgressRef.current[payload.flowId]) {
      return Promise.reject("Request already in progress");
    }

    try {
      requestInProgressRef.current[payload.flowId] = true;
      const config = {};
      config["params"] = { flow_id: payload.flowId };
      const res = await api.get<any>(`${getURL("BUILDS")}`, config);

      if (currentFlow) {
        const newFlowPool = res?.data?.vertex_builds;
        if (Object.keys(newFlowPool).length > 0) {
          // Merge with existing flow pool to preserve duration from SSE events
          const existingFlowPool = useFlowStore.getState().flowPool;
          const mergedFlowPool = { ...newFlowPool };

          // For each vertex, preserve duration from SSE if polling data doesn't have it
          Object.keys(mergedFlowPool).forEach((key) => {
            const existingEntries = existingFlowPool[key];
            const newEntries = mergedFlowPool[key];

            if (existingEntries && newEntries && newEntries.length > 0) {
              // Find duration from existing SSE data
              const existingDuration =
                existingEntries[existingEntries.length - 1]?.data?.duration;

              // If we have duration from SSE but polling doesn't have it, add it
              if (existingDuration && newEntries[newEntries.length - 1]?.data) {
                const lastEntry = newEntries[newEntries.length - 1];
                if (!lastEntry.data.duration) {
                  lastEntry.data.duration = existingDuration;
                }
              }
            }
          });

          setFlowPool(mergedFlowPool);
        }

        if (errorDisplayCountRef.current < MAX_ERROR_DISPLAY_COUNT) {
          Object.keys(newFlowPool).forEach((key) => {
            const nodeBuild = newFlowPool[key];
            if (nodeBuild.length > 0 && nodeBuild[0]?.valid === false) {
              const errorMessage = nodeBuild?.[0]?.params || "Unknown error";
              if (errorMessage) {
                setErrorData({
                  title: "Last build failed",
                  list: [errorMessage],
                });
                errorDisplayCountRef.current = MAX_ERROR_DISPLAY_COUNT;
              }
            }
          });
        }

        return;
      }

      return res.data;
    } finally {
      requestInProgressRef.current[payload.flowId] = false;
    }
  };

  const startPolling = (payload: IGetBuilds) => {
    if (requestInProgressRef.current[payload.flowId]) {
      return Promise.reject("Request already in progress");
    }

    if (!webhookPollingInterval || webhookPollingInterval === 0) {
      return getBuildsFn(payload);
    }

    if (
      flowIdRef.current === payload.flowId &&
      PollingManager.activePolls.has(payload.flowId)
    ) {
      return Promise.resolve({ vertex_builds: {} as FlowPoolType });
    }

    flowIdRef.current = payload.flowId;

    const timestamp = Date.now();
    const pollCallback = async () => {
      const data = await getBuildsFn(payload);
      payload.onSuccess?.(data!);

      if (payload.stopPollingOn?.(data!)) {
        PollingManager.stopPoll(payload.flowId);
      }
    };

    const intervalId = setInterval(pollCallback, webhookPollingInterval);

    const pollingItem: PollingItem = {
      interval: intervalId,
      timestamp,
      flowId: payload.flowId,
      callback: pollCallback,
    };

    PollingManager.enqueuePolling(payload.flowId, pollingItem);

    return getBuildsFn(payload).then((data) => {
      payload.onSuccess?.(data!);
      if (payload.stopPollingOn?.(data!)) {
        PollingManager.stopPoll(payload.flowId);
      }
    });
  };

  useEffect(() => {
    return () => {
      if (flowIdRef.current) {
        PollingManager.stopPoll(flowIdRef.current);
      }
      // Clear all timeouts
      timeoutIdsRef.current.forEach((timeoutId) => {
        clearTimeout(timeoutId);
      });
      timeoutIdsRef.current = [];
      // Reset error display count when component unmounts
      errorDisplayCountRef.current = 0;
    };
  }, []);

  const mutation = mutate(
    ["useGetBuildsMutation"],
    (payload: IGetBuilds) =>
      startPolling(payload) ?? Promise.reject("Failed to start polling"),
    {
      ...options,
      retry: 0,
      retryDelay: 0,
    },
  );

  return mutation;
};

export { PollingManager };
