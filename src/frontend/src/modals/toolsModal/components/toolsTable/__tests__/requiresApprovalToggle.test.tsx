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

  it("should flush a pending toggle when the grid recreates the cell mid-transition", () => {
    const onChange = jest.fn();
    const { unmount } = render(
      <RequiresApprovalToggle selected={[]} onChange={onChange} />,
    );
    fireEvent.click(screen.getByTestId("requires-approval-toggle"));
    unmount();
    expect(onChange).toHaveBeenCalledWith(["approve", "reject"]);
  });

  it("should not flush again on unmount once the transition already persisted", () => {
    const onChange = jest.fn();
    const { unmount } = render(
      <RequiresApprovalToggle selected={[]} onChange={onChange} />,
    );
    fireEvent.click(screen.getByTestId("requires-approval-toggle"));
    act(() => jest.advanceTimersByTime(200));
    unmount();
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("should keep the pending state when the stale row re-renders mid-transition", () => {
    const onChange = jest.fn();
    const { rerender } = render(
      <RequiresApprovalToggle selected={[]} onChange={onChange} />,
    );
    fireEvent.click(screen.getByTestId("requires-approval-toggle"));
    rerender(<RequiresApprovalToggle selected={[]} onChange={onChange} />);
    expect(screen.getByTestId("requires-approval-toggle")).toHaveAttribute(
      "data-state",
      "checked",
    );
    act(() => jest.advanceTimersByTime(200));
    expect(onChange).toHaveBeenCalledWith(["approve", "reject"]);
  });

  it("should follow the row value again once the persist has landed", () => {
    const onChange = jest.fn();
    const { rerender } = render(
      <RequiresApprovalToggle
        selected={["approve", "reject"]}
        onChange={onChange}
      />,
    );
    rerender(<RequiresApprovalToggle selected={[]} onChange={onChange} />);
    expect(screen.getByTestId("requires-approval-toggle")).toHaveAttribute(
      "data-state",
      "unchecked",
    );
  });
});
