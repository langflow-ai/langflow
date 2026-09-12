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

type GridNode = {
  data: { name: string };
  isSelected: () => boolean;
  setSelected: jest.Mock;
};

const setGridOption = jest.fn();

const gridNodes: GridNode[] = [
  {
    data: { name: "search_repositories" },
    isSelected: () => false,
    setSelected: jest.fn(),
  },
  {
    data: { name: "delete_repository" },
    isSelected: () => false,
    setSelected: jest.fn(),
  },
];

const gridApi = {
  setGridOption,
  forEachNode: (callback: (node: GridNode) => void) =>
    gridNodes.forEach(callback),
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

// Stand in for ag-grid: hand ToolsTable a grid api it can drive, report ready so the
// selection effect runs, and expose the suppression prop the grid was configured with.
jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: React.forwardRef(
      (
        props: {
          suppressRowClickSelection?: boolean;
          onGridReady?: () => void;
        },
        ref: React.Ref<unknown>,
      ) => {
        React.useImperativeHandle(ref, () => ({ api: gridApi }));
        React.useEffect(() => {
          props.onGridReady?.();
          // biome-ignore lint/correctness/useExhaustiveDependencies: fire once, like onGridReady
        }, []);
        return (
          <div
            data-testid="grid"
            data-suppress={String(props.suppressRowClickSelection)}
          />
        );
      },
    ),
  }),
);

jest.mock("@/utils/stringManipulation", () => ({
  parseString: (str: string) => str,
  sanitizeMcpName: (str: string) => str,
}));

const rows = [
  {
    name: "search_repositories",
    display_name: "Search Repositories",
    description: "Search repositories by name.",
    display_description: "Search repositories by name.",
    status: true,
    tags: ["search_repositories"],
    readonly: false,
  },
  {
    name: "delete_repository",
    display_name: "Delete Repository",
    description: "Permanently delete a repository.",
    display_description: "Permanently delete a repository.",
    status: true,
    tags: ["delete_repository"],
    readonly: false,
  },
];

const defaultProps = {
  data: [],
  setData: jest.fn(),
  isAction: false,
  placeholder: "Select tools",
  open: true,
  handleOnNewValue: jest.fn(),
};

describe("ToolsTable row-click selection", () => {
  beforeEach(() => {
    setGridOption.mockClear();
    gridNodes.forEach((node) => node.setSelected.mockClear());
  });

  it("should keep row-click selection suppressed for the whole modal", () => {
    render(<ToolsTable {...defaultProps} rows={rows} />);

    // Guard against a vacuous pass: the selection effect must actually have run.
    expect(
      gridNodes.some((node) => node.setSelected.mock.calls.length > 0),
    ).toBe(true);

    // Re-enabling click selection let a click on an already-selected row collapse the
    // selection to that one row, which set status:false on every other tool and
    // silently dropped them from the toolset.
    expect(setGridOption).not.toHaveBeenCalledWith(
      "suppressRowClickSelection",
      false,
    );
  });

  it("should configure the grid to suppress row-click selection", () => {
    render(<ToolsTable {...defaultProps} rows={rows} />);
    expect(screen.getAllByTestId("grid")[0]).toHaveAttribute(
      "data-suppress",
      "true",
    );
  });
});
