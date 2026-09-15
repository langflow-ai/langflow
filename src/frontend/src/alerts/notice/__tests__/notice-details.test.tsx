import { render, screen } from "@testing-library/react";
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
});
