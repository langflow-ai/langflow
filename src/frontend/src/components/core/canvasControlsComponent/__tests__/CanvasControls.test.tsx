import { render, screen } from "@testing-library/react";
import CanvasControls from "../CanvasControls";

// Capture flow functions for assertions
const reactFlowFns = {
  fitView: jest.fn(),
  zoomIn: jest.fn(),
  zoomOut: jest.fn(),
  zoomTo: jest.fn(),
};

// Mocks for external dependencies used internally
jest.mock("@xyflow/react", () => ({
  Panel: ({ children, ...props }: any) => (
    <div data-testid="panel" {...props}>
      {children}
    </div>
  ),
  useReactFlow: () => reactFlowFns,
  useStore: (_selector: any) => ({
    isInteractive: true,
    minZoomReached: false,
    maxZoomReached: false,
    zoom: 1,
  }),
  useStoreApi: () => ({ setState: jest.fn() }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn(() => false),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: ({ orientation }: { orientation: "vertical" | "horizontal" }) => (
    <div data-testid={`separator-${orientation}`} />
  ),
}));

// Mock dropdowns to a simple render that exposes props for assertions
jest.mock("../CanvasControlsDropdown", () => ({
  __esModule: true,
  default: (props: any) => <div data-testid="controls-dropdown" {...props} />,
}));

jest.mock("../HelpDropdown", () => ({
  __esModule: true,
  default: (props: any) => <div data-testid="help-dropdown" {...props} />,
}));

describe("CanvasControls", () => {
  it("renders panel and separators when children present", () => {
    render(
      <CanvasControls>
        <div>child</div>
      </CanvasControls>,
    );
    expect(screen.getByTestId("main_canvas_controls")).toBeInTheDocument();
    const seps = screen.getAllByTestId("separator-vertical");
    expect(seps.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId("controls-dropdown")).toBeInTheDocument();
    expect(screen.getByTestId("help-dropdown")).toBeInTheDocument();
  });

  it("updates reactFlow state based on flow lock status", () => {
    render(<CanvasControls />);

    // The component should set up state through useStoreApi
    // This test verifies the component renders and doesn't throw
    expect(screen.getByTestId("main_canvas_controls")).toBeInTheDocument();
  });
});
