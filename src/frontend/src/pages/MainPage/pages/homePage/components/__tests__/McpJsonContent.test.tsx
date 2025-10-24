import { fireEvent, render, screen } from "@testing-library/react";
import { McpJsonContent } from "../McpJsonContent";

jest.mock("react-syntax-highlighter", () => ({
  Light: ({ children }: { children: string }) => (
    <pre data-testid="syntax-highlighter">{children}</pre>
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

jest.mock("@/components/ui/tabs-button", () => ({
  Tabs: ({
    children,
    onValueChange,
  }: {
    children: React.ReactNode;
    onValueChange: (v: string) => void;
  }) => (
    <div data-testid="tabs" data-onchange={onValueChange}>
      {children}
    </div>
  ),
  TabsList: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TabsTrigger: ({
    children,
    value,
    onClick,
  }: {
    children: React.ReactNode;
    value: string;
    onClick?: () => void;
  }) => (
    <button data-testid={`tab-${value}`} onClick={onClick}>
      {children}
    </button>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: (string | boolean | undefined)[]) =>
    args.filter(Boolean).join(" "),
}));

const defaultProps = {
  selectedPlatform: "macoslinux",
  setSelectedPlatform: jest.fn(),
  isDarkMode: false,
  isCopied: false,
  copyToClipboard: jest.fn(),
  mcpJson: '{"mcpServers": {}}',
  isAuthApiKey: false,
  apiKey: "",
  isGeneratingApiKey: false,
  generateApiKey: jest.fn(),
};

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
    expect(screen.getByTestId("tabs")).toBeInTheDocument();
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

  it("renders with copy state", () => {
    const { container } = render(
      <McpJsonContent {...defaultProps} isCopied={false} />,
    );
    expect(container).toBeInTheDocument();
  });

  it("renders with copied state", () => {
    const { container } = render(
      <McpJsonContent {...defaultProps} isCopied={true} />,
    );
    expect(container).toBeInTheDocument();
  });
});
