import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import useAlertStore from "@/stores/alertStore";
import { axe } from "@/utils/a11y-test";

// SingleAlert pulls in react-markdown (ESM-only in jest); notification body
// rendering is not under test here — only the dropdown's own controls.
jest.mock("../components/singleAlertComponent", () => ({
  __esModule: true,
  default: ({ dropItem }: { dropItem: { title: string } }) => (
    <div>{dropItem.title}</div>
  ),
}));

import AlertDropdown from "../index";

const openDropdown = async () => {
  const user = userEvent.setup();
  render(
    <AlertDropdown>
      <button>bell</button>
    </AlertDropdown>,
  );
  await act(async () => {
    await user.click(screen.getByText("bell"));
  });
};

describe("AlertDropdown accessibility", () => {
  beforeEach(() => {
    act(() => {
      useAlertStore.setState({ notificationList: [] });
    });
  });

  it("labels_the_clear_notifications_button", async () => {
    await openDropdown();

    expect(
      screen.getByRole("button", { name: "Clear notifications" }),
    ).toBeInTheDocument();
  });

  it("labels_the_close_notifications_button", async () => {
    await openDropdown();

    expect(
      screen.getByRole("button", { name: "Close notifications" }),
    ).toBeInTheDocument();
  });

  it("clears_the_notification_list_when_clear_is_clicked", async () => {
    const user = userEvent.setup();
    act(() => {
      useAlertStore.setState({
        notificationList: [
          { id: "1", type: "success", title: "Flow saved successfully!" },
        ],
      });
    });

    render(
      <AlertDropdown>
        <button>bell</button>
      </AlertDropdown>,
    );
    await act(async () => {
      await user.click(screen.getByText("bell"));
    });

    expect(screen.getByText("Flow saved successfully!")).toBeInTheDocument();

    await act(async () => {
      await user.click(
        screen.getByRole("button", { name: "Clear notifications" }),
      );
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 150));
    });

    expect(useAlertStore.getState().notificationList).toHaveLength(0);
  });

  it("closes_the_dropdown_when_close_is_clicked", async () => {
    const onClose = jest.fn();
    const user = userEvent.setup();

    render(
      <AlertDropdown onClose={onClose}>
        <button>bell</button>
      </AlertDropdown>,
    );
    await act(async () => {
      await user.click(screen.getByText("bell"));
    });

    expect(
      screen.getByRole("button", { name: "Close notifications" }),
    ).toBeInTheDocument();

    await act(async () => {
      await user.click(
        screen.getByRole("button", { name: "Close notifications" }),
      );
    });

    expect(onClose).toHaveBeenCalled();
  });

  it("renders_empty_state_when_there_are_no_notifications", async () => {
    await openDropdown();

    expect(screen.getByText("Notifications")).toBeInTheDocument();
  });

  it("should_have_no_axe_violations_when_open", async () => {
    await openDropdown();
    await screen.findByRole("button", { name: "Close notifications" });

    // Radix portals the popover content to document.body, outside the
    // render container, and the region rule is a page-level landmark
    // concern that a bare unit render cannot satisfy.
    expect(
      await axe(document.body, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });
});
