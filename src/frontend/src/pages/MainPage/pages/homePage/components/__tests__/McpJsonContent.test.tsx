import { fireEvent, render, screen } from "@testing-library/react";
import { McpJsonContent } from "../McpJsonContent";

jest.mock("react-syntax-highlighter", () => ({
  Light: ({
    children,
    CodeTag,
  }: {
    children: string;
    CodeTag?: React.ComponentType<{ children: React.ReactNode }>;
  }) => (
    <pre data-testid="syntax-highlighter">
      {CodeTag ? <CodeTag>{children}</CodeTag> : children}
    </pre>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({
    name,
    dataTestId,
  }: {
    name: string;
    dataTestId?: string;
  }) => <span data-testid={dataTestId || `icon-${name}`}>{name}</span>,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    loading,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    loading?: boolean;
  }) => (
    <button onClick={onClick} disabled={disabled} data-loading={loading}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/tabs-button", () => {
  const React = require("react");

  const cloneChildrenWith = (
    children: React.ReactNode,
    extraProps: Record<string, unknown>,
  ) =>
    React.Children.map(children, (child) =>
      React.isValidElement(child)
        ? React.cloneElement(child, extraProps)
        : child,
    );

  const Tabs = ({
    children,
    onValueChange,
  }: {
    children: React.ReactNode;
    onValueChange: (v: string) => void;
  }) => (
    <div data-testid="tabs">
      {cloneChildrenWith(children, { __onValueChange: onValueChange })}
    </div>
  );

  const TabsList = ({
    children,
    __onValueChange,
  }: {
    children: React.ReactNode;
    __onValueChange?: (v: string) => void;
  }) => <div>{cloneChildrenWith(children, { __onValueChange })}</div>;

  const TabsTrigger = ({
    children,
    value,
    onClick,
    __onValueChange,
  }: {
    children: React.ReactNode;
    value: string;
    onClick?: () => void;
    __onValueChange?: (v: string) => void;
  }) => (
    <button
      data-testid={`tab-${value}`}
      onClick={() => {
        onClick?.();
        __onValueChange?.(value);
      }}
    >
      {children}
    </button>
  );

  return {
    Tabs,
    TabsList,
    TabsTrigger,
  };
});

jest.mock("@/utils/utils", () => ({
  cn: (...args: (string | boolean | undefined)[]) =>
    args.filter(Boolean).join(" "),
}));

const defaultProps = {
  selectedPlatform: "macoslinux",
  setSelectedPlatform: jest.fn(),
  selectedTransport: "sse",
  setSelectedTransport: jest.fn(),
  isDarkMode: false,
  isCopied: false,
  copyToClipboard: jest.fn(),
  mcpJson: '{"mcpServers": {}}',
  isAuthApiKey: false,
  apiKey: "",
  isGeneratingApiKey: false,
  generateApiKey: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe("McpJsonContent", () => {
  it("renders JSON content", () => {
    render(<McpJsonContent {...defaultProps} />);
    expect(screen.getByTestId("syntax-highlighter")).toBeInTheDocument();
  });

  it("renders all platform tabs", () => {
    render(<McpJsonContent {...defaultProps} />);
    expect(screen.getByTestId("tab-macoslinux")).toBeInTheDocument();
    expect(screen.getByTestId("tab-windows")).toBeInTheDocument();
    expect(screen.getByTestId("tab-wsl")).toBeInTheDocument();
  });

  it("renders setup guide link", () => {
    render(<McpJsonContent {...defaultProps} />);
    const link = screen.getByText("setup guide").closest("a");
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("docs.langflow.org"),
    );
  });

  it("renders with selected platform", () => {
    render(<McpJsonContent {...defaultProps} selectedPlatform="windows" />);
    expect(screen.getAllByTestId("tabs").length).toBeGreaterThanOrEqual(2);
  });

  it("renders with dark mode", () => {
    render(<McpJsonContent {...defaultProps} isDarkMode={true} />);
    expect(screen.getByTestId("syntax-highlighter")).toBeInTheDocument();
  });

  it("renders with mcpJson prop", () => {
    const json = '{"mcpServers": {"test": {"command": "uvx"}}}';
    render(<McpJsonContent {...defaultProps} mcpJson={json} />);
    expect(screen.getByTestId("syntax-highlighter")).toHaveTextContent(
      "mcpServers",
    );
  });

  it("renders copy icon with PascalCase name and lowercase testid", () => {
    render(<McpJsonContent {...defaultProps} isCopied={false} />);
    const icon = screen.getByTestId("icon-copy");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveTextContent("Copy");
  });

  it("renders check icon with PascalCase name and lowercase testid when copied", () => {
    render(<McpJsonContent {...defaultProps} isCopied={true} />);
    const icon = screen.getByTestId("icon-check");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveTextContent("Check");
  });

  it("invokes setSelectedPlatform when platform tab clicked", () => {
    const setSelectedPlatform = jest.fn();
    render(
      <McpJsonContent
        {...defaultProps}
        setSelectedPlatform={setSelectedPlatform}
      />,
    );
    fireEvent.click(screen.getByTestId("tab-windows"));
    expect(setSelectedPlatform).toHaveBeenCalledWith("windows");
  });

  it("invokes setSelectedTransport when transport tab clicked", () => {
    render(<McpJsonContent {...defaultProps} />);
    fireEvent.click(screen.getByTestId("tab-streamablehttp"));
    expect(defaultProps.setSelectedTransport).toHaveBeenCalledWith(
      "streamablehttp",
    );
  });
});
