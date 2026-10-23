import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TriggerActionMenu from "../TriggerActionMenu";
import TriggerStatusSummary from "../TriggerStatusSummary";
import { makeTrigger } from "./fixtures";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

describe("TriggerActionMenu", () => {
  const openMenu = async (trigger = makeTrigger()) => {
    const onAction = jest.fn();
    const user = userEvent.setup();
    render(
      <TriggerActionMenu trigger={trigger} busy={false} onAction={onAction} />,
    );
    await user.click(
      screen.getByRole("button", { name: "Actions for Slack: On Message" }),
    );
    return { onAction, user };
  };

  it("runs an allowed action", async () => {
    const { onAction, user } = await openMenu();

    await user.click(screen.getByTestId("trigger-action-pause"));

    expect(onAction).toHaveBeenCalledWith(
      expect.objectContaining({ id: "trg-1" }),
      "pause",
    );
  });

  it("keeps a blocked action visible and focusable, with its reason, and does nothing on select", async () => {
    const { onAction, user } = await openMenu();
    const reconnect = screen.getByTestId("trigger-action-reconnect");

    expect(reconnect).toHaveAttribute("aria-disabled", "true");
    expect(reconnect).toHaveAccessibleDescription(
      "The connection is healthy. Reconnect turns on when access is revoked.",
    );
    await user.click(reconnect);
    expect(onAction).not.toHaveBeenCalled();
  });

  it("does not render an action that does not apply", async () => {
    await openMenu();

    expect(screen.queryByTestId("trigger-action-rotate_secret")).toBeNull();
    expect(screen.queryByTestId("trigger-action-resume")).toBeNull();
  });

  it("always offers events and the flow", async () => {
    await openMenu(makeTrigger({ allowed_actions: [], blocked_actions: {} }));

    expect(
      screen.getByTestId("trigger-action-view_events"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("trigger-action-open_flow")).toBeInTheDocument();
    expect(screen.queryByTestId("trigger-action-delete")).toBeNull();
  });
});

describe("TriggerStatusSummary", () => {
  it("offers the server-allowed fix inline", async () => {
    const onFix = jest.fn();
    const trigger = makeTrigger({
      state: "needs_reconnect",
      reason: "needs_reconnect",
      allowed_actions: ["pause", "reconnect", "delete"],
    });
    render(<TriggerStatusSummary trigger={trigger} onFix={onFix} />);

    expect(screen.getByTestId("trigger-state-badge")).toHaveTextContent(
      "Needs reconnect",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Reconnect Slack: On Message" }),
    );
    expect(onFix).toHaveBeenCalledWith(trigger, "reconnect");
  });

  it("shows a dead trigger as Error with the dead reason and no fix", () => {
    render(
      <TriggerStatusSummary
        trigger={makeTrigger({
          state: "dead",
          reason: "dead",
          allowed_actions: ["delete"],
          blocked_actions: { resume: "dead", test: "dead" },
        })}
        onFix={jest.fn()}
      />,
    );

    expect(screen.getByTestId("trigger-state-badge")).toHaveTextContent(
      "Error",
    );
    expect(screen.getByText(/stopped permanently/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("renders the last error as text, never markup", () => {
    const { container } = render(
      <TriggerStatusSummary
        trigger={makeTrigger({ last_error: '<img src=x onerror="alert(1)">' })}
      />,
    );

    expect(screen.getByTestId("trigger-last-error")).toHaveTextContent(
      '<img src=x onerror="alert(1)">',
    );
    expect(container.querySelector("img")).toBeNull();
  });

  it("explains a running trigger only when asked", () => {
    const { rerender } = render(
      <TriggerStatusSummary trigger={makeTrigger()} />,
    );
    expect(screen.queryByText("Listening for events.")).toBeNull();

    rerender(<TriggerStatusSummary trigger={makeTrigger()} explainRunning />);
    expect(screen.getByText("Listening for events.")).toBeInTheDocument();
  });
});
