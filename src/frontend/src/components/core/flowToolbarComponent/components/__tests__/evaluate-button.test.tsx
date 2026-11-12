import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useUtilityStore } from "@/stores/utilityStore";
import EvaluateButton from "../evaluate-button";

const mockSaveFlow = jest.fn();
const mockSetErrorData = jest.fn();

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => mockSaveFlow,
}));
jest.mock("@/contexts/permissionsContext", () => ({
  usePermissions: () => ({ can: () => true }),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: { setErrorData: jest.Mock }) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: "flow-1" }),
}));
// The modal is exercised on its own; here it only has to show that it opened.
jest.mock("@/modals/evaluateFlowModal", () => ({
  __esModule: true,
  default: () => <div data-testid="evaluate-modal" />,
}));

describe("EvaluateButton", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useUtilityStore.setState({ featureFlags: { evals: true } });
  });
  afterEach(() => useUtilityStore.setState({ featureFlags: {} }));

  it("should_keep_an_accessible_name_when_only_the_icon_shows", () => {
    render(<EvaluateButton hasIO />);

    expect(screen.getByTestId("evaluate-btn-flow")).toHaveAccessibleName(
      "Evaluate",
    );
  });

  it("should_save_the_flow_then_open_the_dialog", async () => {
    mockSaveFlow.mockResolvedValueOnce(undefined);
    render(<EvaluateButton hasIO />);

    await userEvent.click(screen.getByTestId("evaluate-btn-flow"));

    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
    expect(await screen.findByTestId("evaluate-modal")).toBeInTheDocument();
  });

  it("should_report_a_failed_save_and_not_evaluate_a_stale_draft", async () => {
    mockSaveFlow.mockRejectedValueOnce(new Error("save failed"));
    render(<EvaluateButton hasIO />);

    await userEvent.click(screen.getByTestId("evaluate-btn-flow"));

    expect(mockSetErrorData).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Could not save the flow before evaluating it",
      }),
    );
    expect(screen.queryByTestId("evaluate-modal")).toBeNull();
  });
});
