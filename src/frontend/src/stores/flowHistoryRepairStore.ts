import { create } from "zustand";

/** Save failures the server can resolve itself when asked to. */
export type FlowHistoryProblemCode =
  | "FLOW_REVISION_MISMATCH"
  | "FLOW_GRAPH_INVALID";

export type FlowHistoryProblem = {
  code: FlowHistoryProblemCode;
  /** For FLOW_GRAPH_INVALID: which graph breaks the rules. */
  graph?: "stored" | "submitted";
  /** For FLOW_GRAPH_INVALID: the broken rules, as codes. */
  violations?: string[];
  /** Resend the refused save with the matching repair flag. */
  repair: () => Promise<void>;
};

interface FlowHistoryRepairState {
  problem: FlowHistoryProblem | null;
  setProblem: (problem: FlowHistoryProblem | null) => void;
}

const useFlowHistoryRepairStore = create<FlowHistoryRepairState>((set) => ({
  problem: null,
  setProblem: (problem) => set({ problem }),
}));

export default useFlowHistoryRepairStore;

type ErrorDetail = {
  code?: string;
  graph?: "stored" | "submitted";
  violations?: { code: string }[];
};

/** Read a repairable problem out of a failed save's response, if it is one. */
export function repairableProblem(
  // biome-ignore lint/suspicious/noExplicitAny: axios error shape
  error: any,
): Omit<FlowHistoryProblem, "repair"> | null {
  const detail: ErrorDetail | undefined = error?.response?.data?.detail;
  if (detail?.code === "FLOW_REVISION_MISMATCH") {
    return { code: "FLOW_REVISION_MISMATCH" };
  }
  if (detail?.code === "FLOW_GRAPH_INVALID") {
    return {
      code: "FLOW_GRAPH_INVALID",
      graph: detail.graph,
      violations: [...new Set(detail.violations?.map((v) => v.code) ?? [])],
    };
  }
  return null;
}
