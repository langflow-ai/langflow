import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
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

  it("offers Resume after reconnecting without repeating the stale connection error", async () => {
    const onFix = jest.fn();
    const trigger = makeTrigger({
      state: "needs_reconnect",
      reason: "ready_to_resume",
      last_error:
        "The connection was revoked or expired. Reconnect it to resume this trigger.",
      allowed_actions: ["pause", "resume", "delete"],
      blocked_actions: { reconnect: "reconnect_not_needed" },
    });
    render(<TriggerStatusSummary trigger={trigger} onFix={onFix} />);

    expect(screen.getByTestId("trigger-state-badge")).toHaveTextContent(
      "Ready to resume",
    );
    expect(
      screen.getByText(
        "The connection is ready. Resume this trigger to listen for events.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("trigger-last-error")).toBeNull();
    expect(screen.queryByTestId("trigger-fix-reconnect")).toBeNull();

    await userEvent.click(
      screen.getByRole("button", { name: "Resume Slack: On Message" }),
    );
    expect(onFix).toHaveBeenCalledWith(trigger, "resume");
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

  it("shows a coded server error in the reader's language, not as the server wrote it", () => {
    render(
      <TriggerStatusSummary
        trigger={makeTrigger({
          state: "pending",
          reason: "config_invalid",
          last_error:
            "Invalid cron expression: a valid five-field cron expression is required.",
          last_error_code: "invalid_cron",
        })}
      />,
    );

    expect(screen.getByTestId("trigger-last-error")).toHaveTextContent(
      "Invalid cron expression: enter five fields (minute, hour, day of month, month, day of week).",
    );
  });

  it("does not repeat a removed node under the reason that already says so", () => {
    render(
      <TriggerStatusSummary
        trigger={makeTrigger({
          state: "paused",
          reason: "node_removed",
          last_error: "trigger node removed from the flow",
          last_error_code: "node_removed",
        })}
      />,
    );

    expect(
      screen.getByText("The trigger node was removed from the flow."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("trigger-last-error")).toBeNull();
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

describe("TriggerActionMenu focus return", () => {
  /** A row menu whose View events and Delete each open a dialog, as on the Triggers page. */
  function MenuWithDialog() {
    const [open, setOpen] = useState<string | null>(null);
    return (
      <>
        <TriggerActionMenu
          trigger={makeTrigger()}
          busy={false}
          onAction={(_trigger, action) => setOpen(action)}
        />
        <Dialog
          open={open !== null}
          onOpenChange={(next) => !next && setOpen(null)}
        >
          <DialogContent>
            <DialogTitle>{open}</DialogTitle>
          </DialogContent>
        </Dialog>
      </>
    );
  }

  it.each(["trigger-action-view_events", "trigger-action-delete"])(
    "returns focus to the row's actions button when %s's dialog closes with Escape",
    async (testId) => {
      const user = userEvent.setup();
      render(<MenuWithDialog />);
      const menuButton = screen.getByRole("button", {
        name: "Actions for Slack: On Message",
      });

      menuButton.focus();
      await user.keyboard("{Enter}");
      screen.getByTestId(testId).focus();
      await user.keyboard("{Enter}");
      expect(await screen.findByRole("dialog")).toBeInTheDocument();

      await user.keyboard("{Escape}");

      await waitFor(() =>
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
      );
      expect(menuButton).toHaveFocus();
    },
  );
});
