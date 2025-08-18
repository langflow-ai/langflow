import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import CanvasControlsDropdown from "../CanvasControlsDropdown";
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
    <div data-testid="dropdown-content" {...props}>
      {children}
    </div>
  ),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: () => <div data-testid="separator" />,
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

describe("CanvasControlsDropdown", () => {
  const baseProps = {
    zoom: 1,
    minZoomReached: false,
    maxZoomReached: false,
    isOpen: true,
    onOpenChange: jest.fn(),
    onZoomIn: jest.fn(),
    onZoomOut: jest.fn(),
    onResetZoom: jest.fn(),
    onFitView: jest.fn(),
    shortcuts: {
      ZOOM_IN: { key: "+" },
      ZOOM_OUT: { key: "-" },
      RESET_ZOOM: { key: "0" },
      FIT_VIEW: { key: "1" },
    },
  };

  it("renders zoom percentage and calls handlers", () => {
    render(<CanvasControlsDropdown {...baseProps} />);
    expect(screen.getByText("100%")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("zoom_in_dropdown"));
    fireEvent.click(screen.getByTestId("zoom_out_dropdown"));
    fireEvent.click(screen.getByTestId("reset_zoom_dropdown"));
    fireEvent.click(screen.getByTestId("fit_view_dropdown"));

    expect(baseProps.onZoomIn).toHaveBeenCalled();
    expect(baseProps.onZoomOut).toHaveBeenCalled();
    expect(baseProps.onResetZoom).toHaveBeenCalled();
    expect(baseProps.onFitView).toHaveBeenCalled();
  });

  it("disables buttons based on min/max zoom flags", () => {
    render(
      <CanvasControlsDropdown
        {...baseProps}
        minZoomReached={true}
        maxZoomReached={true}
      />,
    );
    expect(screen.getByTestId("zoom_in_dropdown")).toBeDisabled();
    expect(screen.getByTestId("zoom_out_dropdown")).toBeDisabled();
  });
});

describe("HelpDropdown", () => {
  beforeEach(() => {
    (window.open as jest.Mock).mockClear();
  });

  it("opens docs in new tab and navigates to shortcuts", () => {
    const mockNavigate = jest.fn();
    (useNavigate as unknown as jest.Mock).mockReturnValue(mockNavigate);

    render(
      <MemoryRouter>
        <HelpDropdown isOpen={true} onOpenChange={() => {}} />
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
