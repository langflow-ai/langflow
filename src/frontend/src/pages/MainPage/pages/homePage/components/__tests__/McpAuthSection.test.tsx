import { fireEvent, render, screen } from "@testing-library/react";
import { McpAuthSection } from "../McpAuthSection";

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
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) => <button onClick={onClick}>{children}</button>,
}));

jest.mock("@/utils/mcpUtils", () => ({
  AUTH_METHODS: {
    apikey: { label: "API Key" },
    oauth: { label: "OAuth" },
  },
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: (string | boolean | undefined)[]) =>
    args.filter(Boolean).join(" "),
}));

describe("McpAuthSection", () => {
  it("renders without authentication", () => {
    render(
      <McpAuthSection
        hasAuthentication={false}
        isLoading={false}
        setAuthModalOpen={jest.fn()}
      />,
    );
    expect(screen.getByText("Auth:")).toBeInTheDocument();
    expect(screen.getByText("None (public)")).toBeInTheDocument();
  });

  it("shows Add Auth button when no authentication", () => {
    render(
      <McpAuthSection
        hasAuthentication={false}
        isLoading={false}
        setAuthModalOpen={jest.fn()}
      />,
    );
    expect(screen.getByText("Add Auth")).toBeInTheDocument();
  });

  it("shows Edit Auth button when authenticated", () => {
    render(
      <McpAuthSection
        hasAuthentication={true}
        isLoading={false}
        currentAuthSettings={{ auth_type: "apikey" }}
        setAuthModalOpen={jest.fn()}
      />,
    );
    expect(screen.getByText("Edit Auth")).toBeInTheDocument();
  });

  it("displays API Key label for apikey auth", () => {
    render(
      <McpAuthSection
        hasAuthentication={true}
        isLoading={false}
        currentAuthSettings={{ auth_type: "apikey" }}
        setAuthModalOpen={jest.fn()}
      />,
    );
    expect(screen.getByText("API Key")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    render(
      <McpAuthSection
        hasAuthentication={true}
        isLoading={true}
        currentAuthSettings={{ auth_type: "apikey" }}
        setAuthModalOpen={jest.fn()}
      />,
    );
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("calls setAuthModalOpen when button clicked", () => {
    const mockSetOpen = jest.fn();
    render(
      <McpAuthSection
        hasAuthentication={false}
        isLoading={false}
        setAuthModalOpen={mockSetOpen}
      />,
    );

    fireEvent.click(screen.getByText("Add Auth"));
    expect(mockSetOpen).toHaveBeenCalledWith(true);
  });
});
