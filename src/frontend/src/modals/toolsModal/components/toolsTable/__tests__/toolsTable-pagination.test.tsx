import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import ToolsTable from "../index";

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: any) => <span data-testid={`icon-${name}`}>{name}</span>,
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: any) => <div>{children}</div>,
}));

jest.mock("@/components/ui/input", () => ({
  Input: ({ value, onChange, placeholder, icon }: any) => (
    <input
      data-testid="search-input"
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      data-icon={icon}
    />
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, ...props }: any) => (
    <button onClick={onClick} data-testid={props["data-testid"]}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/textarea", () => ({
  Textarea: ({ value, onChange }: any) => (
    <textarea data-testid="textarea" value={value} onChange={onChange} />
  ),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: () => <hr data-testid="separator" />,
}));

jest.mock("@/components/ui/sidebar", () => ({
  Sidebar: ({ children }: any) => <div data-testid="sidebar">{children}</div>,
  SidebarContent: ({ children }: any) => <div>{children}</div>,
  SidebarFooter: ({ children }: any) => <div>{children}</div>,
  SidebarGroup: ({ children }: any) => <div>{children}</div>,
  SidebarGroupContent: ({ children }: any) => <div>{children}</div>,
  useSidebar: () => ({ setOpen: jest.fn() }),
}));

// Mock TableComponent to test that pagination props are passed correctly
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: React.forwardRef((props: any, ref: any) => (
      <div data-testid="table-component">
        <div data-testid="pagination-enabled">{String(props.pagination)}</div>
        <div data-testid="pagination-page-size">{props.paginationPageSize}</div>
        <div data-testid="pagination-page-size-selector">
          {JSON.stringify(props.paginationPageSizeSelector)}
        </div>
        <div data-testid="row-count">{props.rowData.length}</div>
      </div>
    )),
  }),
);

jest.mock("@/utils/stringManipulation", () => ({
  parseString: (str: string) => str,
  sanitizeMcpName: (str: string) => str,
}));

describe("ToolsTable - Pagination Tests", () => {
  const mockHandleOnNewValue = jest.fn();

  // Generate mock data with many tools to test pagination
  const generateMockTools = (count: number) => {
    return Array.from({ length: count }, (_, i) => ({
      name: `tool_${i}`,
      display_name: `Tool ${i}`,
      description: `Description for tool ${i}`,
      display_description: `Display description for tool ${i}`,
      status: false,
      tags: [`tag${i}`],
      readonly: false,
    }));
  };

  const defaultProps = {
    data: [],
    setData: jest.fn(),
    isAction: false,
    placeholder: "Select tools",
    open: true,
    handleOnNewValue: mockHandleOnNewValue,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should render with pagination enabled", () => {
    const rows = generateMockTools(100);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    const paginationEnabled = screen.getByTestId("pagination-enabled");
    expect(paginationEnabled.textContent).toBe("true");
  });

  it("should set pagination page size to 50", () => {
    const rows = generateMockTools(100);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    const pageSize = screen.getByTestId("pagination-page-size");
    expect(pageSize.textContent).toBe("50");
  });

  it("should use fixed page size without selector", () => {
    const rows = generateMockTools(100);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    // Verify fixed page size is set
    const pageSize = screen.getByTestId("pagination-page-size");
    expect(pageSize.textContent).toBe("50");

    // Selector should not be present when using fixed page size
    const pageSizeSelector = screen.queryByTestId(
      "pagination-page-size-selector",
    );
    expect(pageSizeSelector?.textContent || "").toBe("");
  });

  it("should handle large datasets (400+ tools) efficiently", () => {
    // Simulating GitHub component with 400 tools
    const rows = generateMockTools(400);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    // Verify pagination is enabled for better performance with large datasets
    const paginationEnabled = screen.getByTestId("pagination-enabled");
    expect(paginationEnabled.textContent).toBe("true");

    // Verify pagination settings are appropriate for large datasets
    const pageSize = screen.getByTestId("pagination-page-size");
    expect(pageSize.textContent).toBe("50");
  });

  it("should handle small datasets with pagination", () => {
    const rows = generateMockTools(10);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    // Pagination should be enabled even for small datasets
    const paginationEnabled = screen.getByTestId("pagination-enabled");
    expect(paginationEnabled.textContent).toBe("true");

    // Verify table component is rendered
    expect(screen.getByTestId("table-component")).toBeInTheDocument();
  });

  it("should maintain table options with pagination", () => {
    const rows = generateMockTools(50);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    // Verify TableComponent is rendered with correct props
    const tableComponent = screen.getByTestId("table-component");
    expect(tableComponent).toBeInTheDocument();
  });

  it("should render search input for filtering tools", () => {
    const rows = generateMockTools(100);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    const searchInput = screen.getByTestId("search-input");
    expect(searchInput).toBeInTheDocument();
    expect(searchInput).toHaveAttribute("placeholder", "Search tools...");
  });

  it("should support both action and non-action modes with pagination", () => {
    const rows = generateMockTools(100);

    const { rerender } = render(
      <ToolsTable {...defaultProps} rows={rows} isAction={false} />,
    );

    let paginationEnabled = screen.getByTestId("pagination-enabled");
    expect(paginationEnabled.textContent).toBe("true");

    rerender(<ToolsTable {...defaultProps} rows={rows} isAction={true} />);

    paginationEnabled = screen.getByTestId("pagination-enabled");
    expect(paginationEnabled.textContent).toBe("true");
  });

  it("should verify pagination options match TableComponent interface", () => {
    const rows = generateMockTools(200);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    // Verify all required pagination props are present
    expect(screen.getByTestId("pagination-enabled")).toBeInTheDocument();
    expect(screen.getByTestId("pagination-page-size")).toBeInTheDocument();
  });

  it("should handle edge case with exactly 50 tools (one page)", () => {
    const rows = generateMockTools(50);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    // With exactly 50 tools and page size of 50, should show all on one page
    const pageSize = screen.getByTestId("pagination-page-size");
    expect(pageSize.textContent).toBe("50");

    const paginationEnabled = screen.getByTestId("pagination-enabled");
    expect(paginationEnabled.textContent).toBe("true");
  });

  it("should handle edge case with 51 tools (two pages)", () => {
    const rows = generateMockTools(51);

    render(<ToolsTable {...defaultProps} rows={rows} />);

    // With 51 tools and page size of 50, should have 2 pages
    const paginationEnabled = screen.getByTestId("pagination-enabled");
    expect(paginationEnabled.textContent).toBe("true");

    const pageSize = screen.getByTestId("pagination-page-size");
    expect(pageSize.textContent).toBe("50");
  });
});
