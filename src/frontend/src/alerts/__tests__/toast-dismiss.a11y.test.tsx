import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import ErrorAlert from "../error";
import NoticeAlert from "../notice";
import SuccessAlert from "../success";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));

jest.mock("../../components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));

const DISMISS_NAME = "Dismiss notification";

describe("Toast dismiss accessibility", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it("should_expose_a_named_dismiss_button_on_the_error_toast", () => {
    render(
      <ErrorAlert
        id="err-1"
        title="Build failed"
        list={[]}
        removeAlert={jest.fn()}
      />,
    );

    const dismiss = screen.getByRole("button", { name: DISMISS_NAME });
    expect(dismiss).toBeInTheDocument();
    dismiss.focus();
    expect(dismiss).toHaveFocus();
  });

  it("should_remove_the_error_toast_exactly_once_when_dismissed", () => {
    const removeAlert = jest.fn();
    render(
      <ErrorAlert
        id="err-1"
        title="Build failed"
        list={[]}
        removeAlert={removeAlert}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: DISMISS_NAME }));
    jest.advanceTimersByTime(500);

    // stopPropagation keeps the container's click-to-dismiss from firing too.
    expect(removeAlert).toHaveBeenCalledTimes(1);
    expect(removeAlert).toHaveBeenCalledWith("err-1");
  });

  it("should_expose_a_named_dismiss_button_on_the_success_toast", () => {
    const removeAlert = jest.fn();
    render(
      <SuccessAlert id="ok-1" title="Flow saved" removeAlert={removeAlert} />,
    );

    fireEvent.click(screen.getByRole("button", { name: DISMISS_NAME }));

    expect(removeAlert).toHaveBeenCalledTimes(1);
    expect(removeAlert).toHaveBeenCalledWith("ok-1");
  });

  it("should_expose_a_named_dismiss_button_on_the_notice_toast", () => {
    const removeAlert = jest.fn();
    render(
      <NoticeAlert id="info-1" title="Heads up" removeAlert={removeAlert} />,
    );

    fireEvent.click(screen.getByRole("button", { name: DISMISS_NAME }));
    jest.advanceTimersByTime(500);

    expect(removeAlert).toHaveBeenCalledTimes(1);
    expect(removeAlert).toHaveBeenCalledWith("info-1");
  });

  it("should_keep_auto_dismiss_timing_at_five_seconds", () => {
    const removeAlert = jest.fn();
    render(
      <SuccessAlert id="ok-2" title="Flow saved" removeAlert={removeAlert} />,
    );

    jest.advanceTimersByTime(4999);
    expect(removeAlert).not.toHaveBeenCalled();

    jest.advanceTimersByTime(1);
    jest.advanceTimersByTime(500);
    expect(removeAlert).toHaveBeenCalledWith("ok-2");
  });

  it("should_have_no_axe_violations", async () => {
    jest.useRealTimers();
    const { container } = render(
      <ErrorAlert
        id="err-2"
        title="Build failed"
        list={[]}
        removeAlert={jest.fn()}
      />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
