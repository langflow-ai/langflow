import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import SessionSelector from "../session-selector";

const mockUpdateSessionName = jest.fn();

jest.mock("@/controllers/API/queries/messages/use-rename-session", () => ({
  __esModule: true,
  useUpdateSessionName: () => ({ mutate: mockUpdateSessionName }),
}));

jest.mock("@/modals/IOModal/hooks/useGetFlowId", () => ({
  __esModule: true,
  useGetFlowId: () => "flow-1",
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (
    selector: (state: { setNewChatOnPlayground: () => void }) => unknown,
  ) => selector({ setNewChatOnPlayground: jest.fn() }),
}));

jest.mock("@/stores/voiceStore", () => ({
  __esModule: true,
  useVoiceStore: (
    selector: (state: {
      setNewSessionCloseVoiceAssistant: () => void;
    }) => unknown,
  ) => selector({ setNewSessionCloseVoiceAssistant: jest.fn() }),
}));

const renderSessionSelector = (
  overrides: Partial<{
    isVisible: boolean;
  }> = {},
) =>
  render(
    <TooltipProvider>
      <SessionSelector
        session="session-1"
        toggleVisibility={jest.fn()}
        isVisible={overrides.isVisible ?? false}
        inspectSession={jest.fn()}
        updateVisibleSession={jest.fn()}
        setSelectedView={jest.fn()}
        playgroundPage={false}
        setActiveSession={jest.fn()}
        deleteSession={jest.fn()}
      />
    </TooltipProvider>,
  );

describe("SessionSelector accessibility", () => {
  beforeAll(() => {
    if (!Element.prototype.hasPointerCapture) {
      Element.prototype.hasPointerCapture = jest.fn(() => false);
    }
    if (!Element.prototype.releasePointerCapture) {
      Element.prototype.releasePointerCapture = jest.fn();
    }
    if (!Element.prototype.scrollIntoView) {
      Element.prototype.scrollIntoView = jest.fn();
    }
  });

  it("has no detectable axe violations in the default (view) state", async () => {
    const { container } = renderSessionSelector();

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("names the row's options trigger as a combobox", () => {
    renderSessionSelector();

    expect(
      screen.getByRole("combobox", { name: "Options" }),
    ).toBeInTheDocument();
  });

  it("switches to editing mode and exposes named cancel/confirm buttons", async () => {
    const user = userEvent.setup();
    renderSessionSelector();

    await user.click(screen.getByRole("combobox", { name: "Options" }));
    await user.click(screen.getByRole("option", { name: /rename/i }));

    const cancelButton = screen.getByRole("button", {
      name: "Cancel rename",
    });
    const confirmButton = screen.getByRole("button", {
      name: "Confirm rename",
    });
    expect(cancelButton).toBeInTheDocument();
    expect(confirmButton).toBeInTheDocument();
  });

  it("has no detectable axe violations while in editing mode", async () => {
    const user = userEvent.setup();
    const { container } = renderSessionSelector();

    await user.click(screen.getByRole("combobox", { name: "Options" }));
    await user.click(screen.getByRole("option", { name: /rename/i }));

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("returns to the read-only row and discards the edit on Cancel", async () => {
    const user = userEvent.setup();
    renderSessionSelector();

    await user.click(screen.getByRole("combobox", { name: "Options" }));
    await user.click(screen.getByRole("option", { name: /rename/i }));
    await user.type(screen.getByRole("textbox"), "renamed");
    await user.click(screen.getByRole("button", { name: "Cancel rename" }));

    expect(
      screen.queryByRole("button", { name: "Cancel rename" }),
    ).not.toBeInTheDocument();
    expect(mockUpdateSessionName).not.toHaveBeenCalled();
  });

  it("commits the rename via the named Confirm button", async () => {
    const user = userEvent.setup();
    renderSessionSelector();

    await user.click(screen.getByRole("combobox", { name: "Options" }));
    await user.click(screen.getByRole("option", { name: /rename/i }));

    const input = screen.getByRole("textbox");
    await user.clear(input);
    await user.type(input, "renamed-session");
    await user.click(screen.getByRole("button", { name: "Confirm rename" }));

    expect(mockUpdateSessionName).toHaveBeenCalledWith(
      { old_session_id: "session-1", new_session_id: "renamed-session" },
      expect.anything(),
    );
  });
});
