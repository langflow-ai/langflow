import { act, fireEvent, render, screen } from "@testing-library/react";
import SingleAlert from "@/alerts/alertDropDown/components/singleAlertComponent";
import NoticeAlert from "@/alerts/notice";

const message =
  "Custom components are disabled (LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false). This run uses the server's Agent code. The saved flow is unchanged.";

describe("notice details", () => {
  it("renders the full policy warning in the toast", () => {
    render(
      <NoticeAlert
        id="warning"
        title="Workflow warning"
        list={[message]}
        removeAlert={jest.fn()}
      />,
    );
    expect(screen.getByText(message)).toBeVisible();
  });

  it("renders the full policy warning in notification history", () => {
    render(
      <SingleAlert
        dropItem={{
          id: "warning",
          type: "notice",
          title: "Workflow warning",
          list: [message],
        }}
        removeAlert={jest.fn()}
      />,
    );
    expect(screen.getByText(message)).toBeVisible();
  });

  it("keeps the details open when clicked and still supports explicit dismissal", () => {
    jest.useFakeTimers();
    try {
      const removeAlert = jest.fn();
      render(
        <NoticeAlert
          id="warning"
          title="Workflow warning"
          list={[message]}
          removeAlert={removeAlert}
        />,
      );

      fireEvent.click(screen.getByText(message));
      act(() => jest.advanceTimersByTime(500));
      expect(removeAlert).not.toHaveBeenCalled();
      expect(screen.getByText(message)).toBeVisible();

      fireEvent.click(screen.getByRole("button"));
      act(() => jest.advanceTimersByTime(500));
      expect(removeAlert).toHaveBeenCalledWith("warning");
    } finally {
      jest.useRealTimers();
    }
  });
});
