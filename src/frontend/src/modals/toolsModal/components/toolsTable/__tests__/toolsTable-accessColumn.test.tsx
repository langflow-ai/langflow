import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import React from "react";
import ToolsTable from "../index";

type Children = { children?: ReactNode };
type InputLike = {
  value?: string;
  placeholder?: string;
  onChange?: (
    event: React.ChangeEvent<HTMLInputElement & HTMLTextAreaElement>,
  ) => void;
};

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name?: string }) => <span>{name}</span>,
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: Children) => <div>{children}</div>,
}));

jest.mock("@/components/ui/input", () => ({
  Input: ({ value, onChange, placeholder }: InputLike) => (
    <input value={value} onChange={onChange} placeholder={placeholder} />
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children }: Children) => <button type="button">{children}</button>,
}));

jest.mock("@/components/ui/textarea", () => ({
  Textarea: ({ value, onChange }: InputLike) => (
    <textarea value={value} onChange={onChange} />
  ),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: () => <hr />,
}));

jest.mock("@/components/ui/sidebar", () => ({
  Sidebar: ({ children }: Children) => <div>{children}</div>,
  SidebarContent: ({ children }: Children) => <div>{children}</div>,
  SidebarFooter: ({ children }: Children) => <div>{children}</div>,
  SidebarGroup: ({ children }: Children) => <div>{children}</div>,
  SidebarGroupContent: ({ children }: Children) => <div>{children}</div>,
  useSidebar: () => ({ setOpen: jest.fn() }),
}));

// Report the column order the table was handed, so the assertions read the real
// columnDefs rather than ag-grid's rendered output.
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: React.forwardRef(
      (props: { columnDefs: { field?: string }[] }, _ref: unknown) => (
        <div data-testid="column-fields">
          {props.columnDefs.map((col) => col.field).join(",")}
        </div>
      ),
    ),
  }),
);

jest.mock("@/utils/stringManipulation", () => ({
  parseString: (str: string) => str,
  sanitizeMcpName: (str: string) => str,
}));

const tool = (extra: Record<string, unknown> = {}) => ({
  name: "fetch",
  display_name: "Fetch",
  description: "Fetch a page",
  display_description: "Fetch a page",
  status: true,
  tags: ["fetch"],
  readonly: false,
  ...extra,
});

const defaultProps = {
  data: [],
  setData: jest.fn(),
  isAction: false,
  placeholder: "Select tools",
  open: true,
  handleOnNewValue: jest.fn(),
};

const columnFields = () =>
  (screen.getByTestId("column-fields").textContent ?? "").split(",");

describe("ToolsTable access column", () => {
  it("should omit the column when no tool declares a hint", () => {
    render(<ToolsTable {...defaultProps} rows={[tool(), tool()]} />);
    expect(columnFields()).not.toContain("access_hint");
  });

  it("should show the column when a tool declares a hint", () => {
    render(
      <ToolsTable
        {...defaultProps}
        rows={[tool(), tool({ access_hint: "destructive" })]}
      />,
    );
    expect(columnFields()).toContain("access_hint");
  });

  it("should keep the column adjacent to the approval toggle", () => {
    render(
      <ToolsTable
        {...defaultProps}
        rows={[tool({ access_hint: "read_only" })]}
      />,
    );
    const fields = columnFields();
    expect(fields.indexOf("approval_actions")).toBe(
      fields.indexOf("access_hint") + 1,
    );
  });
});
