import { render, screen } from "@testing-library/react";
import { McpFlowsSection } from "../McpFlowsSection";

jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/ToolsComponent",
  () => ({
    __esModule: true,
    default: ({ value }: { value: Array<{ id: string }> }) => (
      <div data-testid="tools-component">Tools: {value.length}</div>
    ),
  }),
);

describe("McpFlowsSection", () => {
  it("renders flows/tools label", () => {
    render(<McpFlowsSection flowsMCPData={[]} handleOnNewValue={jest.fn()} />);
    expect(screen.getByText("Flows/Tools")).toBeInTheDocument();
  });

  it("renders ToolsComponent with flows data", () => {
    const flows = [
      { id: "1", name: "test", description: "test desc", status: true },
    ];
    render(
      <McpFlowsSection flowsMCPData={flows} handleOnNewValue={jest.fn()} />,
    );
    expect(screen.getByTestId("tools-component")).toBeInTheDocument();
    expect(screen.getByText("Tools: 1")).toBeInTheDocument();
  });

  it("renders with empty flows array", () => {
    render(<McpFlowsSection flowsMCPData={[]} handleOnNewValue={jest.fn()} />);
    expect(screen.getByText("Tools: 0")).toBeInTheDocument();
  });
});
