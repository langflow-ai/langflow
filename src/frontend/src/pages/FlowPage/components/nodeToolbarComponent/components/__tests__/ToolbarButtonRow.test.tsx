import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { ToolbarButtonRow } from "../ToolbarButtonRow";

let lastShadTooltipPropsByContent: Array<Record<string, unknown>> = [];
let lastToggleProps: Record<string, unknown> = {};

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    children,
    ...props
  }: {
    children: ReactNode;
    [key: string]: unknown;
  }) => {
    lastShadTooltipPropsByContent.push(props);
    return <>{children}</>;
  },
}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/toggleShadComponent",
  () => ({
    __esModule: true,
    default: (props: Record<string, unknown>) => {
      lastToggleProps = props;
      return <span data-testid="tool-mode-toggle" />;
    },
  }),
);

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    asChild: _asChild,
    ...props
  }: {
    children: ReactNode;
    asChild?: boolean;
  }) => <div {...props}>{children}</div>,
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_INSPECTION_PANEL: false,
}));

jest.mock("@/stores/shortcuts", () => ({
  useShortcutsStore: (selector: (state: { shortcuts: unknown[] }) => unknown) =>
    selector({
      shortcuts: [{ name: "Tool Mode", shortcut: "T" }],
    }),
}));

jest.mock("../../shortcutDisplay", () => ({
  __esModule: true,
  default: ({ name }: { name?: string }) => <span>{name}</span>,
}));

const baseProps = {
  canEditCode: false,
  isCustomComponent: false,
  onCode: jest.fn(),
  onToggleInspectionPanel: jest.fn(),
  inspectionPanelVisible: false,
  hasToolMode: true,
  frozen: false,
  onFreeze: jest.fn(),
  toolMode: false,
  onToolMode: jest.fn(),
};

describe("ToolbarButtonRow — tool mode button", () => {
  beforeEach(() => {
    lastShadTooltipPropsByContent = [];
    lastToggleProps = {};
  });

  it("should_suppress_the_tooltips_aria_describedby_so_the_shortcut_text_is_not_read_out_alongside_the_button", () => {
    render(<ToolbarButtonRow {...baseProps} />);

    // Exactly one ShadTooltip renders in this row when hasToolMode is true.
    expect(lastShadTooltipPropsByContent).toHaveLength(1);
    const props = lastShadTooltipPropsByContent[0];
    expect("ariaDescribedBy" in props).toBe(true);
    expect(props.ariaDescribedBy).toBeUndefined();
  });

  it("should_toggle_on_click", () => {
    const onToolMode = jest.fn();
    render(<ToolbarButtonRow {...baseProps} onToolMode={onToolMode} />);

    fireEvent.click(screen.getByRole("button", { name: "Tool Mode" }));

    expect(onToolMode).toHaveBeenCalledTimes(1);
  });

  it("should_toggle_on_enter_and_space_since_a_plain_div_does_not_natively_activate_on_keydown", () => {
    const onToolMode = jest.fn();
    render(<ToolbarButtonRow {...baseProps} onToolMode={onToolMode} />);
    const button = screen.getByRole("button", { name: "Tool Mode" });

    fireEvent.keyDown(button, { key: "Enter" });
    fireEvent.keyDown(button, { key: " " });

    expect(onToolMode).toHaveBeenCalledTimes(2);
  });

  it("should_not_toggle_on_an_unrelated_key", () => {
    const onToolMode = jest.fn();
    render(<ToolbarButtonRow {...baseProps} onToolMode={onToolMode} />);

    fireEvent.keyDown(screen.getByRole("button", { name: "Tool Mode" }), {
      key: "Tab",
    });

    expect(onToolMode).not.toHaveBeenCalled();
  });

  it("should_expose_its_own_pressed_state_now_that_the_nested_switch_is_hidden_from_assistive_tech", () => {
    render(<ToolbarButtonRow {...baseProps} toolMode={true} />);

    expect(screen.getByRole("button", { name: "Tool Mode" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("should_pull_the_nested_switch_out_of_tab_order_so_the_outer_button_is_the_only_focus_stop", () => {
    render(<ToolbarButtonRow {...baseProps} />);

    expect(lastToggleProps.tabIndex).toBe(-1);
  });

  it("should_hide_the_nested_switch_from_the_accessibility_tree", () => {
    render(<ToolbarButtonRow {...baseProps} />);

    expect(
      screen.getByTestId("tool-mode-toggle").parentElement,
    ).toHaveAttribute("aria-hidden", "true");
  });
});
