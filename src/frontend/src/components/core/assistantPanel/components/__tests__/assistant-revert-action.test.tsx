/**
 * Revert action on an assistant message: active button opens a confirmation
 * dialog, confirming delegates to useAssistantRevert (mocked here — the
 * snapshot-then-restore ordering is covered by the hook's own tests), and a
 * reverted message renders the disabled "Reverted" marker instead.
 */

import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const revertMock = jest.fn();
jest.mock("../../hooks/use-assistant-revert", () => ({
  useAssistantRevert: () => ({ revert: revertMock, isReverting: false }),
}));

import { AssistantRevertAction } from "../assistant-revert-action";

describe("AssistantRevertAction", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    revertMock.mockResolvedValue(undefined);
  });

  it("should_render_the_revert_button_when_not_reverted", () => {
    render(
      <AssistantRevertAction
        restoreVersionId="ver-1"
        reverted={false}
        onReverted={jest.fn()}
      />,
    );

    expect(screen.getByTestId("assistant-revert-button")).toBeInTheDocument();
    expect(screen.queryByTestId("assistant-revert-reverted")).toBeNull();
    expect(screen.queryByTestId("assistant-revert-confirm")).toBeNull();
  });

  it("should_open_the_confirmation_dialog_on_click", () => {
    render(
      <AssistantRevertAction
        restoreVersionId="ver-1"
        reverted={false}
        onReverted={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("assistant-revert-button"));

    expect(screen.getByTestId("assistant-revert-confirm")).toBeInTheDocument();
    expect(revertMock).not.toHaveBeenCalled();
  });

  it("should_call_revert_with_the_version_id_on_confirm_and_mark_reverted_on_success", async () => {
    revertMock.mockImplementation(
      async (_id: string, options?: { onSuccess?: () => void }) => {
        options?.onSuccess?.();
      },
    );
    const onReverted = jest.fn();
    render(
      <AssistantRevertAction
        restoreVersionId="ver-1"
        reverted={false}
        onReverted={onReverted}
      />,
    );

    fireEvent.click(screen.getByTestId("assistant-revert-button"));
    fireEvent.click(screen.getByTestId("assistant-revert-confirm-button"));

    await waitFor(() => {
      expect(revertMock).toHaveBeenCalledWith("ver-1", {
        onSuccess: onReverted,
      });
    });
    expect(onReverted).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByTestId("assistant-revert-confirm")).toBeNull();
    });
  });

  it("should_close_the_dialog_without_reverting_on_cancel", async () => {
    render(
      <AssistantRevertAction
        restoreVersionId="ver-1"
        reverted={false}
        onReverted={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByTestId("assistant-revert-button"));
    fireEvent.click(screen.getByTestId("assistant-revert-cancel"));

    await waitFor(() => {
      expect(screen.queryByTestId("assistant-revert-confirm")).toBeNull();
    });
    expect(revertMock).not.toHaveBeenCalled();
  });

  it("should_keep_the_dialog_open_and_not_mark_reverted_when_revert_fails", async () => {
    revertMock.mockRejectedValue(new Error("restore failed"));
    const onReverted = jest.fn();
    render(
      <AssistantRevertAction
        restoreVersionId="ver-1"
        reverted={false}
        onReverted={onReverted}
      />,
    );

    fireEvent.click(screen.getByTestId("assistant-revert-button"));
    fireEvent.click(screen.getByTestId("assistant-revert-confirm-button"));

    await waitFor(() => {
      expect(revertMock).toHaveBeenCalled();
    });
    expect(onReverted).not.toHaveBeenCalled();
    expect(screen.getByTestId("assistant-revert-confirm")).toBeInTheDocument();
  });

  it("should_render_the_disabled_reverted_marker_when_reverted", () => {
    render(
      <AssistantRevertAction
        restoreVersionId="ver-1"
        reverted={true}
        onReverted={jest.fn()}
      />,
    );

    expect(screen.getByTestId("assistant-revert-reverted")).toBeInTheDocument();
    expect(screen.queryByTestId("assistant-revert-button")).toBeNull();
  });
});
