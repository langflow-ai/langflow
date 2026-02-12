import { render, screen, fireEvent } from "@testing-library/react";
import { SessionMoreMenu } from "../session-more-menu";

let lastSelectProps: Record<string, unknown> = {};
let lastTriggerProps: Record<string, unknown> = {};

jest.mock("@/components/ui/select-custom", () => ({
  Select: ({
    children,
    onValueChange,
    ...props
  }: {
    children: React.ReactNode;
    onValueChange?: (value: string) => void;
    [key: string]: unknown;
  }) => {
    lastSelectProps = { onValueChange, ...props };
    return <div data-testid="select-root">{children}</div>;
  },
  SelectTrigger: ({
    children,
    className,
    ...props
  }: {
    children: React.ReactNode;
    className?: string;
    [key: string]: unknown;
  }) => {
    lastTriggerProps = { className, ...props };
    return (
      <button
        data-testid={props["data-testid"] ?? "select-trigger"}
        className={className}
        aria-disabled={props["aria-disabled"] as boolean}
        aria-label={props["aria-label"] as string}
        onClick={props.onClick as React.MouseEventHandler}
      >
        {children}
      </button>
    );
  },
  SelectContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="select-content">{children}</div>
  ),
  SelectItem: ({
    children,
    value,
    ...props
  }: {
    children: React.ReactNode;
    value: string;
    [key: string]: unknown;
  }) => (
    <div
      data-testid={props["data-testid"] as string}
      onClick={() => lastSelectProps.onValueChange?.(value)}
      role="option"
    >
      {children}
    </div>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const defaultProps = {
  onRename: jest.fn(),
  onMessageLogs: jest.fn(),
  onDelete: jest.fn(),
  onClearChat: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
  lastSelectProps = {};
  lastTriggerProps = {};
});

describe("SessionMoreMenu visibility", () => {
  it("should_render_all_options_when_all_show_flags_are_true", () => {
    render(
      <SessionMoreMenu
        {...defaultProps}
        showRename={true}
        showMessageLogs={true}
        showDelete={true}
        showClearChat={true}
      />,
    );

    expect(screen.getByTestId("rename-session-option")).toBeInTheDocument();
    expect(screen.getByTestId("message-logs-option")).toBeInTheDocument();
    expect(screen.getByTestId("delete-session-option")).toBeInTheDocument();
    expect(screen.getByTestId("clear-chat-option")).toBeInTheDocument();
  });

  it("should_hide_rename_when_showRename_is_false", () => {
    render(
      <SessionMoreMenu
        {...defaultProps}
        showRename={false}
        showMessageLogs={true}
        showDelete={true}
      />,
    );

    expect(screen.queryByTestId("rename-session-option")).not.toBeInTheDocument();
    expect(screen.getByTestId("message-logs-option")).toBeInTheDocument();
    expect(screen.getByTestId("delete-session-option")).toBeInTheDocument();
  });

  it("should_hide_message_logs_when_showMessageLogs_is_false", () => {
    render(
      <SessionMoreMenu
        {...defaultProps}
        showRename={true}
        showMessageLogs={false}
        showDelete={true}
      />,
    );

    expect(screen.getByTestId("rename-session-option")).toBeInTheDocument();
    expect(
      screen.queryByTestId("message-logs-option"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("delete-session-option")).toBeInTheDocument();
  });

  it("should_only_show_delete_for_shareable_playground_non_default_session", () => {
    render(
      <SessionMoreMenu
        {...defaultProps}
        showRename={false}
        showMessageLogs={false}
        showDelete={true}
        showClearChat={false}
      />,
    );

    expect(screen.queryByTestId("rename-session-option")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("message-logs-option"),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("clear-chat-option")).not.toBeInTheDocument();
    expect(screen.getByTestId("delete-session-option")).toBeInTheDocument();
  });
});

describe("SessionMoreMenu disabled state", () => {
  it("should_apply_disabled_styles_when_disabled_is_true", () => {
    render(
      <SessionMoreMenu {...defaultProps} disabled={true} showDelete={true} />,
    );

    const trigger = screen.getByTestId("select-trigger");
    expect(trigger.className).toContain("pointer-events-none");
    expect(trigger.className).toContain("opacity-50");
    expect(trigger.getAttribute("aria-disabled")).toBe("true");
  });

  it("should_not_apply_disabled_styles_when_disabled_is_false", () => {
    render(
      <SessionMoreMenu {...defaultProps} disabled={false} showDelete={true} />,
    );

    const trigger = screen.getByTestId("select-trigger");
    expect(trigger.className).not.toContain("pointer-events-none");
    expect(trigger.className).not.toContain("opacity-50");
  });
});

describe("SessionMoreMenu actions", () => {
  it("should_call_onRename_when_rename_option_is_selected", () => {
    render(
      <SessionMoreMenu {...defaultProps} showRename={true} showDelete={true} />,
    );

    fireEvent.click(screen.getByTestId("rename-session-option"));
    expect(defaultProps.onRename).toHaveBeenCalledTimes(1);
  });

  it("should_call_onDelete_when_delete_option_is_selected", () => {
    render(
      <SessionMoreMenu {...defaultProps} showRename={true} showDelete={true} />,
    );

    fireEvent.click(screen.getByTestId("delete-session-option"));
    expect(defaultProps.onDelete).toHaveBeenCalledTimes(1);
  });

  it("should_call_onClearChat_when_clear_option_is_selected", () => {
    render(
      <SessionMoreMenu
        {...defaultProps}
        showClearChat={true}
        showDelete={true}
      />,
    );

    fireEvent.click(screen.getByTestId("clear-chat-option"));
    expect(defaultProps.onClearChat).toHaveBeenCalledTimes(1);
  });

  it("should_call_onMessageLogs_when_logs_option_is_selected", () => {
    render(
      <SessionMoreMenu
        {...defaultProps}
        showMessageLogs={true}
        showDelete={true}
      />,
    );

    fireEvent.click(screen.getByTestId("message-logs-option"));
    expect(defaultProps.onMessageLogs).toHaveBeenCalledTimes(1);
  });
});

describe("SessionMoreMenu custom data-testid", () => {
  it("should_pass_dataTestid_to_trigger", () => {
    render(
      <SessionMoreMenu
        {...defaultProps}
        showDelete={true}
        dataTestid="chat-header-more-menu"
      />,
    );

    expect(
      screen.getByTestId("chat-header-more-menu"),
    ).toBeInTheDocument();
  });
});
