import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps, ReactNode } from "react";
import { ActionPickerAddingContext } from "../addingContext";
import ActionPickerComponent from "../index";

const setErrorData = jest.fn();
const setNoticeData = jest.fn();
const stopAdding = jest.fn();

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
    selector ? selector({ edges: [] }) : {},
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

describe("ActionPickerComponent add flow", () => {
  beforeEach(() => jest.clearAllMocks());

  const baseProps = {
    value: ["Approve", "Reject"],
    handleOnNewValue: jest.fn(),
    nodeId: "node-1",
    id: "actionpicker_test",
  } as unknown as ComponentProps<typeof ActionPickerComponent>;

  const renderAdding = (props: ComponentProps<typeof ActionPickerComponent>) =>
    render(
      <ActionPickerAddingContext.Provider
        value={{ isAdding: true, startAdding: jest.fn(), stopAdding }}
      >
        <ActionPickerComponent {...props} />
      </ActionPickerAddingContext.Provider>,
    );

  it("should show a naming input with a placeholder while adding", () => {
    renderAdding(baseProps);
    expect(
      screen.getByPlaceholderText("Name this choice…"),
    ).toBeInTheDocument();
  });

  it("should size the naming input to fit its full placeholder", () => {
    renderAdding(baseProps);
    const input = screen.getByTestId("action-add-input") as HTMLInputElement;
    // The input must derive its width from the placeholder (HTML size attribute, locale-proof)
    // rather than a fixed w-* class that overrides it and cuts the text to "Name this actio…".
    expect(input.size).toBeGreaterThanOrEqual(input.placeholder.length);
    expect(input.className).not.toMatch(/\bw-\d+\b/);
  });

  it("should add the typed action on Enter and stop adding", () => {
    const handleOnNewValue = jest.fn();
    renderAdding({ ...baseProps, handleOnNewValue });
    const input = screen.getByTestId("action-add-input");
    fireEvent.change(input, { target: { value: "Escalate" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(handleOnNewValue).toHaveBeenCalledWith({
      value: ["Approve", "Reject", "Escalate"],
    });
    expect(stopAdding).toHaveBeenCalled();
  });

  it("should discard an empty name without persisting", () => {
    const handleOnNewValue = jest.fn();
    renderAdding({ ...baseProps, handleOnNewValue });
    const input = screen.getByTestId("action-add-input");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(handleOnNewValue).not.toHaveBeenCalled();
    expect(stopAdding).toHaveBeenCalled();
  });

  it("should reject a duplicate name", () => {
    const handleOnNewValue = jest.fn();
    renderAdding({ ...baseProps, handleOnNewValue });
    const input = screen.getByTestId("action-add-input");
    fireEvent.change(input, { target: { value: "Approve" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(handleOnNewValue).not.toHaveBeenCalled();
    expect(setErrorData).toHaveBeenCalled();
  });
});
