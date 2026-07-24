import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { axe } from "@/utils/a11y-test";
import HelpDropdown from "../HelpDropdown";

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: any) => (
    <button {...props}>{children}</button>
  ),
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children, ...props }: any) => (
    <div data-testid="dropdown-menu" {...props}>
      {children}
    </div>
  ),
  DropdownMenuTrigger: ({ children, ...props }: any) => (
    <div data-testid="dropdown-trigger" {...props}>
      {children}
    </div>
  ),
  DropdownMenuContent: ({ children, ...props }: any) => (
    <div data-testid="dropdown-content" role="menu" {...props}>
      {children}
    </div>
  ),
  DropdownMenuItem: ({ children, onClick, ...props }: any) => (
    <button type="button" role="menuitem" onClick={onClick} {...props}>
      {children}
    </button>
  ),
  DropdownMenuCheckboxItem: ({
    children,
    onCheckedChange,
    checked,
    ...props
  }: any) => (
    <button
      type="button"
      role="menuitemcheckbox"
      aria-checked={checked}
      onClick={() => onCheckedChange?.(!checked)}
      {...props}
    >
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: () => <div data-testid="separator" role="separator" />,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => <span data-testid="icon" />,
  ForwardedIconComponent: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/constants/constants", () => ({
  __esModule: true,
  DATASTAX_DOCS_URL: "https://docs.datastax.com",
  DOCS_URL: "https://docs.langflow.org",
  DESKTOP_URL: "https://desktop.langflow.org",
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_DATASTAX_LANGFLOW: false,
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
  getOS: () => "macos",
}));

jest.mock("react-router-dom", () => {
  const actual = jest.requireActual("react-router-dom");
  return {
    ...actual,
    useNavigate: jest.fn(),
  };
});

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: () => ({
    dark: false,
    setDark: jest.fn(),
  }),
}));

const mockFlowStoreState = {
  helperLineEnabled: false,
  setHelperLineEnabled: jest.fn(),
};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof mockFlowStoreState) => unknown) =>
    selector(mockFlowStoreState),
}));

// Mock window.open
Object.defineProperty(window, "open", {
  writable: true,
  value: jest.fn(),
});

describe("HelpDropdown", () => {
  beforeEach(() => {
    (window.open as jest.Mock).mockClear();
  });

  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <HelpDropdown />
      </MemoryRouter>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("opens docs in new tab and navigates to shortcuts", () => {
    const mockNavigate = jest.fn();
    (useNavigate as unknown as jest.Mock).mockReturnValue(mockNavigate);

    render(
      <MemoryRouter>
        <HelpDropdown/>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByTestId("canvas_controls_dropdown_docs"));
    expect(window.open).toHaveBeenCalledWith(
      "https://docs.langflow.org",
      "_blank",
    );

    fireEvent.click(screen.getByTestId("canvas_controls_dropdown_shortcuts"));
    expect(mockNavigate).toHaveBeenCalledWith("/settings/shortcuts");

    fireEvent.click(
      screen.getByTestId("canvas_controls_dropdown_get_langflow_desktop"),
    );
    expect(window.open).toHaveBeenCalledWith(
      "https://desktop.langflow.org",
      "_blank",
    );
  });
});
