import { fireEvent, render, screen } from "@testing-library/react";
import { SessionSelector } from "../session-selector";

// ---------------------------------------------------------------------------
// Minimal mocks — keep the test focused on the checkbox visibility logic.
// ---------------------------------------------------------------------------

// Override the global no-op mock so we can read the className passed to
// the icon and assert the hover/visibility utility classes are wired.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className} />
  ),
}));

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

describe("SessionSelector — checkbox visibility", () => {
  it("hides the checkbox icon by default and reveals it on row hover", () => {
    render(
      <SessionSelector
        {...baseProps}
        isVisible={false}
        isSelected={false}
        onToggleSelect={jest.fn()}
      />,
    );
    const wrapper = screen.getByTestId(`session-${baseProps.session}-checkbox`);
    const icon = wrapper.firstElementChild as HTMLElement;
    expect(icon.className).toContain("invisible");
    expect(icon.className).toContain("group-hover:visible");
    // The row carries the `group` class so the group-hover utility resolves.
    expect(screen.getByTestId("session-selector").className).toContain("group");
  });

  it("keeps the checkbox icon always visible when the session is selected", () => {
    render(
      <SessionSelector
        {...baseProps}
        isVisible={false}
        isSelected={true}
        onToggleSelect={jest.fn()}
      />,
    );
    const wrapper = screen.getByTestId(`session-${baseProps.session}-checkbox`);
    const icon = wrapper.firstElementChild as HTMLElement;
    expect(icon.className).not.toContain("invisible");
    expect(icon.className).not.toContain("group-hover:visible");
    expect(icon.className).toContain("text-status-red");
  });

  it("still reserves the 16x16 column when the icon is hidden so the layout does not jump", () => {
    render(
      <SessionSelector
        {...baseProps}
        isVisible={false}
        isSelected={false}
        onToggleSelect={jest.fn()}
      />,
    );
    const wrapper = screen.getByTestId(`session-${baseProps.session}-checkbox`);
    expect(wrapper.className).toContain("w-4");
    expect(wrapper.className).toContain("h-4");
  });

  it("toggles selection when the checkbox column is clicked and stops row propagation", () => {
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
    fireEvent.click(
      screen.getByTestId(`session-${baseProps.session}-checkbox`),
    );
    expect(onToggleSelect).toHaveBeenCalledTimes(1);
    // Row click must NOT fire as a side-effect of the checkbox click.
    expect(toggleVisibility).not.toHaveBeenCalled();
  });

  it("does not render a checkbox column when showCheckbox is false", () => {
    render(
      <SessionSelector
        {...baseProps}
        isVisible={false}
        isSelected={false}
        showCheckbox={false}
        onToggleSelect={jest.fn()}
      />,
    );
    expect(
      screen.queryByTestId(`session-${baseProps.session}-checkbox`),
    ).not.toBeInTheDocument();
  });
});
