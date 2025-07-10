import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowPoolType } from "@/types/zustand/flow";
import { useEffect, useRef } from "react";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

const _ERROR_DISPLAY_INTERVAL = 10000;
const _ERROR_DISPLAY_COUNT = 1;

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
        const flowPool = res?.data?.vertex_builds;
        if (Object.keys(flowPool).length > 0) {
          setFlowPool(flowPool);
        }

        // Check for errors only if we haven't displayed them yet
        if (errorDisplayCountRef.current === 0) {
          Object.keys(flowPool).forEach((key) => {
            const nodeBuild = flowPool[key];
            if (nodeBuild.length > 0 && nodeBuild[0]?.valid === false) {
              const errorMessage = nodeBuild?.[0]?.params || "Unknown error";
              if (errorMessage) {
                setErrorData({
                  title: "Last build failed",
                  list: [errorMessage],
                });
                errorDisplayCountRef.current = 1;
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
