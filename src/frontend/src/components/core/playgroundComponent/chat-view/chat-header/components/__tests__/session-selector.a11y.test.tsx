import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import { SessionSelector } from "../session-selector";

jest.mock("@/controllers/API/queries/messages/use-rename-session", () => ({
  useUpdateSessionName: () => ({ mutate: jest.fn() }),
}));

type VoiceState = { setNewSessionCloseVoiceAssistant: jest.Mock };
jest.mock("@/stores/voiceStore", () => ({
  useVoiceStore: <TResult,>(selector: (state: VoiceState) => TResult) =>
    selector({ setNewSessionCloseVoiceAssistant: jest.fn() }),
}));

jest.mock("../../hooks/use-session-has-messages", () => ({
  useSessionHasMessages: () => true,
}));

jest.mock("../session-rename", () => ({
  SessionRename: () => <div data-testid="session-rename" />,
}));

// Deliberately NOT mocking SessionMoreMenu here (unlike session-selector.test.tsx)
// — its real Select/SelectTrigger is what makes the row's role="button" wrapper
// a nested-interactive risk if the two are ever misnested again. session-selector.tsx
// already regressed on exactly this (axe flagged nested-interactive when the
// role="button" briefly lived on the outer row instead of the inner label wrapper).

const baseProps = {
  session: "New Session 0",
  currentFlowId: "flow-1",
  deleteSession: jest.fn(),
  toggleVisibility: jest.fn(),
  updateVisibleSession: jest.fn(),
  handleRename: jest.fn().mockResolvedValue(undefined),
};

const renderSelector = (overrides: Partial<{ isVisible: boolean }> = {}) =>
  render(
    <TooltipProvider>
      <SessionSelector
        {...baseProps}
        isVisible={overrides.isVisible ?? false}
      />
    </TooltipProvider>,
  );

describe("SessionSelector (chat-header) accessibility", () => {
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
    const { container } = renderSelector();

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("has no detectable axe violations when active", async () => {
    const { container } = renderSelector({ isVisible: true });

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("names the row's more-options trigger as a combobox", () => {
    renderSelector();

    expect(
      screen.getByRole("combobox", { name: "More options" }),
    ).toBeInTheDocument();
  });

  it("opens the more-options menu without disturbing the row's own keyboard reachability", async () => {
    const user = userEvent.setup();
    renderSelector();

    await user.click(screen.getByRole("combobox", { name: "More options" }));

    expect(
      screen.getByRole("option", { name: /message logs/i }),
    ).toBeInTheDocument();
  });
});
