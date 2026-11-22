import { act, renderHook } from "@testing-library/react";
import type { Evaluation } from "@/controllers/API/queries/evals/types";
import { useRerun } from "../hooks/use-rerun";

const mockEstimate = jest.fn();
const mockMutate = jest.fn();

jest.mock("@/controllers/API/queries/evals/use-evaluations", () => ({
  useEstimateEvaluation: (params: unknown, options: unknown) => {
    mockEstimate(params, options);
    return { isFetching: true, isPlaceholderData: false, isError: false };
  },
  useStartEvaluationRun: () => ({ mutate: mockMutate, isPending: false }),
}));

const EVALUATION = {
  id: "evaluation-1",
  flow_id: "flow-1",
  dataset_id: "dataset-1",
  scorers: [],
} as unknown as Evaluation;

describe("useRerun", () => {
  beforeEach(() => mockEstimate.mockClear());

  it("should_price_the_version_being_rerun_not_the_draft", () => {
    const { result } = renderHook(() => useRerun(EVALUATION, jest.fn()));

    act(() => result.current.request("version-7"));

    expect(mockEstimate).toHaveBeenLastCalledWith(
      expect.objectContaining({ flowVersionId: "version-7" }),
      { enabled: true },
    );
  });

  it("should_price_the_draft_when_rerunning_the_latest", () => {
    const { result } = renderHook(() => useRerun(EVALUATION, jest.fn()));

    act(() => result.current.request(null));

    expect(mockEstimate).toHaveBeenLastCalledWith(
      expect.objectContaining({ flowVersionId: null }),
      { enabled: true },
    );
  });
});
