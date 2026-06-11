import { render, screen } from "@testing-library/react";
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

jest.mock("../session-more-menu", () => ({
  SessionMoreMenu: () => <div data-testid="session-more-menu" />,
}));

jest.mock("../session-rename", () => ({
  SessionRename: () => <div data-testid="session-rename" />,
}));

const baseProps = {
  session: "New Session 0",
  currentFlowId: "flow-1",
  deleteSession: jest.fn(),
  toggleVisibility: jest.fn(),
  updateVisibleSession: jest.fn(),
  handleRename: jest.fn().mockResolvedValue(undefined),
  onMenuOpenChange: jest.fn(),
  onToggleSelect: jest.fn(),
  showCheckbox: true,
};

const getRoot = () => screen.getByTestId("session-selector");

// Matches `bg-accent` only when used as its own utility, not as a variant
// suffix such as `hover:bg-accent`. The negative lookbehind excludes the
// pseudo-prefix colon so we test the row-level (non-hover) state.
const ROW_BG_ACCENT = /(?<!:)\bbg-accent\b/;

describe("SessionSelector — visual focus cue", () => {
  it("renders neutral styling when the session is neither active nor selected", () => {
    render(
      <SessionSelector {...baseProps} isVisible={false} isSelected={false} />,
    );
    const root = getRoot();
    expect(root).not.toHaveAttribute("aria-current");
    expect(root).not.toHaveAttribute("data-active");
    expect(root.className).toContain("font-normal");
    expect(root.className).not.toMatch(ROW_BG_ACCENT);
  });

  it("highlights only the active session with bg + bold + aria-current", () => {
    render(
      <SessionSelector {...baseProps} isVisible={true} isSelected={false} />,
    );
    const root = getRoot();
    expect(root).toHaveAttribute("aria-current", "page");
    expect(root).toHaveAttribute("data-active", "true");
    expect(root.className).toContain("font-semibold");
    expect(root.className).toMatch(ROW_BG_ACCENT);
  });

  it("keeps the active styling when the session is also checked in multi-select", () => {
    render(
      <SessionSelector {...baseProps} isVisible={true} isSelected={true} />,
    );
    const root = getRoot();
    expect(root).toHaveAttribute("aria-current", "page");
    expect(root.className).toContain("font-semibold");
    expect(root.className).toMatch(ROW_BG_ACCENT);
  });

  it("does NOT add a row background when a non-active session is checked", () => {
    // The red checkbox icon alone signals selection. Adding bg-accent here
    // would make peer-selected rows visually indistinguishable from the
    // single in-focus row — which is the bug this PR fixes.
    render(
      <SessionSelector {...baseProps} isVisible={false} isSelected={true} />,
    );
    const root = getRoot();
    expect(root).not.toHaveAttribute("aria-current");
    expect(root).not.toHaveAttribute("data-active");
    expect(root.className).toContain("font-normal");
    expect(root.className).not.toMatch(ROW_BG_ACCENT);
  });
});
