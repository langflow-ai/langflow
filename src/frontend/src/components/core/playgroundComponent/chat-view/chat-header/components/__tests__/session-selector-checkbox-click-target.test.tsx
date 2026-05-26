import { fireEvent, render, screen } from "@testing-library/react";
import { SessionSelector } from "../session-selector";

jest.mock("@/components/common/genericIconComponent", () => {
  const Icon = ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className} />
  );
  return { __esModule: true, default: Icon, ForwardedIconComponent: Icon };
});

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
  showCheckbox: true,
};

describe("SessionSelector — checkbox click target", () => {
  it("expands the checkbox wrapper to the full row height so clicks above/below the icon still toggle selection", () => {
    render(
      <SessionSelector
        {...baseProps}
        isVisible={false}
        isSelected={false}
        onToggleSelect={jest.fn()}
      />,
    );
    const wrapper = screen.getByTestId(`session-${baseProps.session}-checkbox`);
    // Row height is h-8 (32px); the wrapper must match so clicks 8px
    // above or below the visible 16x16 icon still land inside the
    // checkbox column instead of bubbling to the row.
    expect(wrapper.className).toContain("h-8");
    // Width stays narrow so text alignment is unchanged.
    expect(wrapper.className).toContain("w-4");
    expect(wrapper.className).not.toContain("h-4");
  });

  it("triggers onToggleSelect when the wrapper (not just the icon) is clicked, and does NOT trigger toggleVisibility", () => {
    const onToggleSelect = jest.fn();
    const toggleVisibility = jest.fn();
    render(
      <SessionSelector
        {...baseProps}
        isVisible={false}
        isSelected={false}
        toggleVisibility={toggleVisibility}
        onToggleSelect={onToggleSelect}
      />,
    );
    const wrapper = screen.getByTestId(`session-${baseProps.session}-checkbox`);
    fireEvent.click(wrapper);
    expect(onToggleSelect).toHaveBeenCalledTimes(1);
    expect(toggleVisibility).not.toHaveBeenCalled();
  });

  it("still triggers selection when only the inner icon is clicked", () => {
    const onToggleSelect = jest.fn();
    const toggleVisibility = jest.fn();
    render(
      <SessionSelector
        {...baseProps}
        isVisible={false}
        isSelected={false}
        toggleVisibility={toggleVisibility}
        onToggleSelect={onToggleSelect}
      />,
    );
    const icon = screen.getByTestId("icon-Square");
    fireEvent.click(icon);
    expect(onToggleSelect).toHaveBeenCalledTimes(1);
    expect(toggleVisibility).not.toHaveBeenCalled();
  });
});
