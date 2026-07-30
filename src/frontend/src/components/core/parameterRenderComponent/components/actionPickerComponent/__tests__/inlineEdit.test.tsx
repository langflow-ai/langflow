import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps, ReactNode } from "react";
import ActionPickerComponent from "../index";

const setErrorData = jest.fn();
const setNoticeData = jest.fn();
let mockEdges: Array<{ source: string; sourceHandle: string }> = [];

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector?: (s: {
      setErrorData: jest.Mock;
      setNoticeData: jest.Mock;
    }) => unknown,
  ) => (selector ? selector({ setErrorData, setNoticeData }) : {}),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector?: (s: { edges: unknown[] }) => unknown) =>
    selector ? selector({ edges: mockEdges }) : {},
}));

jest.mock("@/utils/reactflowUtils", () => ({
  scapeJSONParse: (s: string) => JSON.parse(s),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("ActionPickerComponent inline edit", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockEdges = [];
  });

  const baseProps = {
    value: ["Approve", "Escalate"],
    handleOnNewValue: jest.fn(),
    nodeId: "node-1",
    id: "actionpicker_test",
  } as unknown as ComponentProps<typeof ActionPickerComponent>;

  it("should rename an action in place and persist the new list on Enter", () => {
    const handleOnNewValue = jest.fn();
    render(
      <ActionPickerComponent
        {...baseProps}
        handleOnNewValue={handleOnNewValue}
      />,
    );
    fireEvent.click(screen.getByTestId("action-edit-Escalate"));
    const input = screen.getByTestId("action-edit-input-Escalate");
    fireEvent.change(input, { target: { value: "Need More Info" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(handleOnNewValue).toHaveBeenCalledWith({
      value: ["Approve", "Need More Info"],
    });
  });

  it("should reject a rename that duplicates another action", () => {
    const handleOnNewValue = jest.fn();
    render(
      <ActionPickerComponent
        {...baseProps}
        handleOnNewValue={handleOnNewValue}
      />,
    );
    fireEvent.click(screen.getByTestId("action-edit-Escalate"));
    const input = screen.getByTestId("action-edit-input-Escalate");
    fireEvent.change(input, { target: { value: "Approve" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(handleOnNewValue).not.toHaveBeenCalled();
    expect(setErrorData).toHaveBeenCalled();
  });

  it("should warn when renaming an action that has a connected branch edge", () => {
    mockEdges = [
      {
        source: "node-1",
        sourceHandle: JSON.stringify({ name: "branch_escalate" }),
      },
    ];
    render(<ActionPickerComponent {...baseProps} />);
    fireEvent.click(screen.getByTestId("action-edit-Escalate"));
    const input = screen.getByTestId("action-edit-input-Escalate");
    fireEvent.change(input, { target: { value: "Reviewed" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(setNoticeData).toHaveBeenCalled();
  });

  it("should cancel the edit on Escape without persisting", () => {
    const handleOnNewValue = jest.fn();
    render(
      <ActionPickerComponent
        {...baseProps}
        handleOnNewValue={handleOnNewValue}
      />,
    );
    fireEvent.click(screen.getByTestId("action-edit-Approve"));
    const input = screen.getByTestId("action-edit-input-Approve");
    fireEvent.change(input, { target: { value: "Changed" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(handleOnNewValue).not.toHaveBeenCalled();
  });
});
