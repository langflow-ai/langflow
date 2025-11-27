import { fireEvent, render, screen } from "@testing-library/react";
import { McpAutoInstallContent } from "../McpAutoInstallContent";

jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
  }) => (
    <button onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: (string | boolean | undefined)[]) =>
    args.filter(Boolean).join(" "),
}));

jest.mock("@/utils/stringManipulation", () => ({
  toSpaceCase: (str: string) => str,
}));

describe("McpAutoInstallContent", () => {
  it("shows warning when not local connection", () => {
    render(
      <McpAutoInstallContent
        isLocalConnection={false}
        installedMCPData={[]}
        loadingMCP={[]}
        installClient={jest.fn()}
        installedClients={[]}
      />,
    );
    expect(
      screen.getByText(/One-click install is disabled/),
    ).toBeInTheDocument();
  });

  it("does not show warning when is local connection", () => {
    render(
      <McpAutoInstallContent
        isLocalConnection={true}
        installedMCPData={[]}
        loadingMCP={[]}
        installClient={jest.fn()}
        installedClients={[]}
      />,
    );
    expect(
      screen.queryByText(/One-click install is disabled/),
    ).not.toBeInTheDocument();
  });

  it("renders all installer buttons", () => {
    render(
      <McpAutoInstallContent
        isLocalConnection={true}
        installedMCPData={[
          { name: "cursor", available: true },
          { name: "claude", available: true },
          { name: "windsurf", available: true },
        ]}
        loadingMCP={[]}
        installClient={jest.fn()}
        installedClients={[]}
      />,
    );
    expect(screen.getAllByText("Cursor").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Claude").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Windsurf").length).toBeGreaterThan(0);
  });

  it("calls installClient when button clicked", () => {
    const mockInstall = jest.fn();
    render(
      <McpAutoInstallContent
        isLocalConnection={true}
        installedMCPData={[{ name: "cursor", available: true }]}
        loadingMCP={[]}
        installClient={mockInstall}
        installedClients={[]}
      />,
    );

    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);
    expect(mockInstall).toHaveBeenCalledWith("cursor", "Cursor");
  });

  it("disables button when not local connection", () => {
    render(
      <McpAutoInstallContent
        isLocalConnection={false}
        installedMCPData={[{ name: "cursor", available: true }]}
        loadingMCP={[]}
        installClient={jest.fn()}
        installedClients={[]}
      />,
    );

    const buttons = screen.getAllByRole("button");
    expect(buttons[0]).toBeDisabled();
  });

  it("disables button when client not available", () => {
    render(
      <McpAutoInstallContent
        isLocalConnection={true}
        installedMCPData={[{ name: "cursor", available: false }]}
        loadingMCP={[]}
        installClient={jest.fn()}
        installedClients={[]}
      />,
    );

    const buttons = screen.getAllByRole("button");
    expect(buttons[0]).toBeDisabled();
  });

  it("shows check icon for installed clients", () => {
    render(
      <McpAutoInstallContent
        isLocalConnection={true}
        installedMCPData={[{ name: "cursor", available: true }]}
        loadingMCP={[]}
        installClient={jest.fn()}
        installedClients={["cursor"]}
      />,
    );

    expect(screen.getByText("Check")).toBeInTheDocument();
  });

  it("shows loader when client is installing", () => {
    render(
      <McpAutoInstallContent
        isLocalConnection={true}
        installedMCPData={[{ name: "cursor", available: true }]}
        loadingMCP={["cursor"]}
        installClient={jest.fn()}
        installedClients={[]}
      />,
    );

    expect(screen.getByText("Loader2")).toBeInTheDocument();
  });
});
