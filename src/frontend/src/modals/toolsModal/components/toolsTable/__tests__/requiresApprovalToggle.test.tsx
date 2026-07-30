import { act, fireEvent, render, screen } from "@testing-library/react";
import { RequiresApprovalToggle } from "../RequiresApprovalToggle";

describe("RequiresApprovalToggle", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it("should be off when no approval actions are selected", () => {
    render(<RequiresApprovalToggle selected={[]} onChange={jest.fn()} />);
    expect(screen.getByTestId("requires-approval-toggle")).toHaveAttribute(
      "data-state",
      "unchecked",
    );
  });

  it("should be on when approval actions are present", () => {
    render(
      <RequiresApprovalToggle
        selected={["approve", "reject"]}
        onChange={jest.fn()}
      />,
    );
    expect(screen.getByTestId("requires-approval-toggle")).toHaveAttribute(
      "data-state",
      "checked",
    );
  });

  it("should flip its visual state immediately so the slide animates", () => {
    render(<RequiresApprovalToggle selected={[]} onChange={jest.fn()} />);
    fireEvent.click(screen.getByTestId("requires-approval-toggle"));
    expect(screen.getByTestId("requires-approval-toggle")).toHaveAttribute(
      "data-state",
      "checked",
    );
  });

  it("should persist both approve and reject after the transition when turned on", () => {
    const onChange = jest.fn();
    render(<RequiresApprovalToggle selected={[]} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("requires-approval-toggle"));
    act(() => jest.advanceTimersByTime(200));
    expect(onChange).toHaveBeenCalledWith(["approve", "reject"]);
  });

  it("should persist an empty list after the transition when turned off", () => {
    const onChange = jest.fn();
    render(
      <RequiresApprovalToggle
        selected={["approve", "reject"]}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByTestId("requires-approval-toggle"));
    act(() => jest.advanceTimersByTime(200));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
