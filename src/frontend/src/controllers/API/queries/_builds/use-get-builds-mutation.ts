import { useMutationFunctionType } from "@/types/api";
import { FlowPoolType } from "@/types/zustand/flow";
import { useEffect, useRef } from "react";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

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

    const nextPoll = queue[queue.length - 1];
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
  pollingInterval?: number;
  onSuccess?: (data: { vertex_builds: FlowPoolType }) => void;
  stopPollingOn?: (data: { vertex_builds: FlowPoolType }) => boolean;
}

export const useGetBuildsMutation: useMutationFunctionType<
  undefined,
  IGetBuilds
> = (options?) => {
  const { mutate } = UseRequestProcessor();
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const getBuildsFn = async (
    payload: IGetBuilds,
  ): Promise<{ vertex_builds: FlowPoolType }> => {
    const config = {};
    config["params"] = { flow_id: payload.flowId };
    const res = await api.get<any>(`${getURL("BUILDS")}`, config);
    return res.data;
  };

  const startPolling = (payload: IGetBuilds) => {
    if (!payload.pollingInterval) {
      return getBuildsFn(payload);
    }

    const timestamp = Date.now();

    const pollCallback = async () => {
      const data = await getBuildsFn(payload);
      payload.onSuccess?.(data);

      if (payload.stopPollingOn?.(data)) {
        PollingManager.stopPoll(payload.flowId);
      }
    };

    const intervalId = setInterval(
      pollCallback,
      payload.pollingInterval * 1000,
    );
    pollingIntervalRef.current = intervalId;

    const pollingItem: PollingItem = {
      interval: intervalId,
      timestamp,
      flowId: payload.flowId,
      callback: pollCallback,
    };

    PollingManager.enqueuePolling(payload.flowId, pollingItem);

    // Execute initial call
    return getBuildsFn(payload).then((data) => {
      payload.onSuccess?.(data);
      if (payload.stopPollingOn?.(data)) {
        PollingManager.stopPoll(payload.flowId);
      }
    });
  };

  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  const mutation = mutate(
    ["useGetBuildsMutation"],
    (payload: IGetBuilds) =>
      startPolling(payload) ?? Promise.reject("Failed to start polling"),
    options,
  );

  return mutation;
};

export { PollingManager };
