import { fireEvent, render, screen } from "@testing-library/react";
import type { InteractiveContent } from "@/types/chat";
import HumanInputCard from "../HumanInputCard";

const mockResume = jest.fn();
const mockConsume = jest.fn();
const mockSetAwaitingInput = jest.fn();
const mockSetIsBuilding = jest.fn();
const mockSetErrorData = jest.fn();

jest.mock("@/contexts", () => ({
  queryClient: { invalidateQueries: jest.fn() },
}));
jest.mock("@/controllers/API/queries/workflows/use-resume-workflow", () => ({
  useResumeWorkflow: () => ({ mutate: mockResume, isPending: false }),
}));
jest.mock("@/controllers/API/agui/run-flow-bridge", () => ({
  consumeBackgroundEvents: (...args: unknown[]) => mockConsume(...args),
}));
jest.mock("@/controllers/API/agui/human-input-card", () => ({
  getResumeContext: () => ({ jobId: "job-1", opts: { flowId: "f1" } }),
  markHumanInputSubmitted: jest.fn(),
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setAwaitingInput: mockSetAwaitingInput,
      setIsBuilding: mockSetIsBuilding,
    }),
  },
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (s: { setErrorData: unknown }) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));

jest.mock("../../../common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span data-testid={`icon-${name}`} />,
}));

jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children: string }) => <span>{children}</span>,
}));
jest.mock("remark-gfm", () => ({ __esModule: true, default: () => {} }));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
}));
jest.mock("@/components/ui/input", () => ({
  Input: (props: any) => <input {...props} />,
}));

const _approval: InteractiveContent = {
  type: "human_input",
  kind: "tool_approval",
  request_id: "node:job-1",
  prompt: "Approve refund?",
  options: [
    { action_id: "approve", label: "Approve" },
    { action_id: "reject", label: "Reject" },
  ],
  allowed_decisions: ["approve", "reject"],
};

describe("HumanInputCard", () => {
  beforeEach(() => jest.clearAllMocks());

  it("renders the prompt and one button per option", () => {
    render(<HumanInputCard content={_approval} onSubmit={jest.fn()} />);
    expect(screen.getByText("Approve refund?")).toBeInTheDocument();
    expect(screen.getByTestId("human-input-decision-approve")).toBeInTheDocument();
    expect(screen.getByTestId("human-input-decision-reject")).toBeInTheDocument();
  });

  it("submits the chosen action with empty values when there are no form fields", () => {
    const onSubmit = jest.fn();
    render(<HumanInputCard content={_approval} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByTestId("human-input-decision-approve"));
    expect(onSubmit).toHaveBeenCalledWith({ action_id: "approve", values: {} });
  });

  it("disables the controls once submitted", () => {
    const onSubmit = jest.fn();
    render(<HumanInputCard content={_approval} onSubmit={onSubmit} submitted />);
    fireEvent.click(screen.getByTestId("human-input-decision-approve"));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByTestId("human-input-decision-approve")).toBeDisabled();
  });

  it("collects form field values into the decision (node_input)", () => {
    const onSubmit = jest.fn();
    const nodeInput: InteractiveContent = {
      type: "human_input",
      kind: "node_input",
      request_id: "node:job-2",
      prompt: "Pick one",
      options: [
        { action_id: "a", label: "A" },
        { action_id: "b", label: "B" },
        { action_id: "c", label: "C" },
      ],
      schema: [{ name: "reason", type: "str", required: true }],
      allowed_decisions: ["a", "b", "c"],
    };
    render(<HumanInputCard content={nodeInput} onSubmit={onSubmit} />);
    expect(screen.getAllByRole("button")).toHaveLength(3);
    fireEvent.change(screen.getByTestId("human-input-field-reason"), {
      target: { value: "fraud" },
    });
    fireEvent.click(screen.getByTestId("human-input-decision-b"));
    expect(onSubmit).toHaveBeenCalledWith({
      action_id: "b",
      values: { reason: "fraud" },
    });
  });

  it("resumes the run itself when no onSubmit is provided", () => {
    const content: InteractiveContent = { ..._approval, job_id: "job-1" };
    render(<HumanInputCard content={content} />);
    fireEvent.click(screen.getByTestId("human-input-decision-approve"));
    expect(mockResume).toHaveBeenCalledWith(
      {
        jobId: "job-1",
        requestId: "node:job-1",
        decision: { action_id: "approve", values: {} },
      },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    const { onSuccess } = mockResume.mock.calls[0][1];
    onSuccess();
    expect(mockSetAwaitingInput).toHaveBeenCalledWith(false);
    expect(mockSetIsBuilding).toHaveBeenCalledWith(true);
    expect(mockConsume).toHaveBeenCalledWith("job-1", { flowId: "f1" }, undefined, {
      skipCardInjection: true,
    });
  });

  it("disables controls after a self-resume click (single-use)", () => {
    const content: InteractiveContent = { ..._approval, job_id: "job-1" };
    render(<HumanInputCard content={content} />);
    fireEvent.click(screen.getByTestId("human-input-decision-approve"));
    expect(screen.getByTestId("human-input-decision-approve")).toBeDisabled();
  });

  it("renders resolved on reload when content carries submitted_action", () => {
    const content: InteractiveContent = {
      ..._approval,
      job_id: "job-1",
      submitted_action: "approve",
    };
    render(<HumanInputCard content={content} />);
    // Only the chosen option is shown; the others are gone; no resume is fired.
    expect(
      screen.getByTestId("human-input-decision-approve"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("human-input-decision-reject"),
    ).not.toBeInTheDocument();
    expect(mockResume).not.toHaveBeenCalled();
  });

  it("keeps only the chosen option and removes the others after selecting", () => {
    const content: InteractiveContent = { ..._approval, job_id: "job-1" };
    render(<HumanInputCard content={content} />);
    expect(screen.getByTestId("human-input-decision-reject")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("human-input-decision-approve"));
    expect(screen.getByTestId("human-input-decision-approve")).toBeInTheDocument();
    expect(
      screen.queryByTestId("human-input-decision-reject"),
    ).not.toBeInTheDocument();
  });
});
