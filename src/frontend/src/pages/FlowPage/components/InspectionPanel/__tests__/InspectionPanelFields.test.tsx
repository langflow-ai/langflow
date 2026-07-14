import { render, screen } from "@testing-library/react";
import type { NodeDataType } from "@/types/flow";
import InspectionPanelFields from "../components/InspectionPanelFields";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: function MockIconComponent({ name }: any) {
    return <span data-testid={`icon-${name}`}>{name}</span>;
  },
}));

jest.mock("../components/InspectionPanelParameterRow", () => {
  return function MockParameterRow({ name, title }: any) {
    return (
      <div data-testid={`row-${name}`}>
        {title}
      </div>
    );
  };
});

describe("InspectionPanelFields", () => {
  const createMockData = (
    template: Record<string, any>,
    overrides = {},
  ): NodeDataType =>
    ({
      id: "test-node-123",
      type: "TestComponent",
      node: {
        display_name: "Test Node",
        description: "Test description",
        tool_mode: false,
        field_order: Object.keys(template),
        template,
        ...overrides,
      },
    }) as unknown as NodeDataType;

  it("lists every manageable parameter, on-canvas and hidden alike", () => {
    const data = createMockData({
      shown_field: { type: "str", show: true, advanced: false },
      hidden_field: { type: "str", show: true, advanced: true },
    });
    render(<InspectionPanelFields data={data} />);

    expect(screen.getByTestId("row-shown_field")).toBeInTheDocument();
    expect(screen.getByTestId("row-hidden_field")).toBeInTheDocument();
  });

  it("orders on-canvas parameters before hidden ones", () => {
    const data = createMockData({
      a_hidden: { type: "str", show: true, advanced: true },
      b_shown: { type: "str", show: true, advanced: false },
    });
    render(<InspectionPanelFields data={data} />);

    const rows = screen.getAllByTestId(/^row-/);
    expect(rows[0]).toHaveAttribute("data-testid", "row-b_shown");
    expect(rows[1]).toHaveAttribute("data-testid", "row-a_hidden");
  });

  it("excludes internal, code, non-show and readonly fields", () => {
    const data = createMockData({
      _internal: { type: "str", show: true },
      code: { type: "code", show: true },
      invisible: { type: "str", show: false },
      readonly_field: { type: "str", show: true, readonly: true },
      normal: { type: "str", show: true },
    });
    render(<InspectionPanelFields data={data} />);

    expect(screen.getByTestId("row-normal")).toBeInTheDocument();
    expect(screen.queryByTestId("row-_internal")).not.toBeInTheDocument();
    expect(screen.queryByTestId("row-code")).not.toBeInTheDocument();
    expect(screen.queryByTestId("row-invisible")).not.toBeInTheDocument();
    expect(screen.queryByTestId("row-readonly_field")).not.toBeInTheDocument();
  });

  it("excludes tool-mode fields while tool mode is active", () => {
    const data = createMockData(
      {
        tool_field: { type: "str", show: true, tool_mode: true },
        normal: { type: "str", show: true },
      },
      { tool_mode: true },
    );
    render(<InspectionPanelFields data={data} />);

    expect(screen.getByTestId("row-normal")).toBeInTheDocument();
    expect(screen.queryByTestId("row-tool_field")).not.toBeInTheDocument();
  });

  it("hides APIRequest body when method is GET", () => {
    const data = createMockData({
      method: { type: "str", show: true, value: "GET" },
      body: { type: "dict", show: true },
    });
    (data as any).type = "APIRequest";
    render(<InspectionPanelFields data={data} />);

    expect(screen.queryByTestId("row-body")).not.toBeInTheDocument();
  });

  it("shows the empty state when no parameter is manageable", () => {
    const data = createMockData({
      _internal: { type: "str", show: true },
    });
    render(<InspectionPanelFields data={data} />);

    expect(screen.getByText("No parameters")).toBeInTheDocument();
  });

  it("keeps connected fields listed (row handles their disabled state)", () => {
    const data = createMockData({
      connected_field: { type: "str", show: true, advanced: false },
    });
    render(<InspectionPanelFields data={data} />);

    expect(screen.getByTestId("row-connected_field")).toBeInTheDocument();
  });
});
