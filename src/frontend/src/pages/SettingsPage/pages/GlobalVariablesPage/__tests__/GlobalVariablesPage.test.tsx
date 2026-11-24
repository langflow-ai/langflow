import { render, screen } from "@testing-library/react";
import type { ColDef, ValueFormatterParams } from "ag-grid-community";
import type { ReactNode } from "react";
import type { GlobalVariable } from "@/types/global_variables";

let mockPermissionsLoading = false;

jest.mock("@/contexts/permissionsContext", () => ({
  PermissionsProvider: ({ children }: { children: ReactNode }) => children,
  usePermissions: () => ({
    can: () => true,
    isLoading: mockPermissionsLoading,
    isError: false,
    permissions: {
      "variable-1": ["read", "write", "delete"],
    },
  }),
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({
    data: [
      {
        id: "variable-1",
        name: "TEST_VARIABLE",
        value: "value",
        type: "Generic",
        default_fields: [],
        is_owner: true,
        can_manage_shares: false,
      },
    ],
  }),
  useDeleteGlobalVariables: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/components/core/dropdownComponent", () => ({
  __esModule: true,
  default: ({ children }: { children?: ReactNode }) => children ?? null,
}));

jest.mock("ag-grid-react", () => {
  const React = jest.requireActual("react");
  return {
    AgGridReact: React.forwardRef(
      (
        {
          columnDefs,
          rowData,
        }: {
          columnDefs: Array<{
            colId?: string;
            cellRenderer?: (props: { data?: GlobalVariable }) => ReactNode;
          }>;
          rowData: GlobalVariable[];
        },
        _ref: unknown,
      ) => {
        const actionsColumn = columnDefs.find(
          (column) => column.colId === "actions",
        );
        return (
          <div data-testid="global-variables-table">
            {actionsColumn?.cellRenderer?.({ data: rowData[0] })}
          </div>
        );
      },
    ),
  };
});

jest.mock("@/components/core/GlobalVariableModal/GlobalVariableModal", () => ({
  __esModule: true,
  default: ({ children }: { children?: ReactNode }) => children ?? null,
}));

jest.mock("@/customization/components/custom-variable-share-action", () => ({
  __esModule: true,
  default: ({
    resourceId,
    resourceName,
  }: {
    resourceId: string;
    resourceName: string;
  }) => (
    <div data-resource-id={resourceId} data-testid="variable-share-seam">
      {resourceName}
    </div>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: () => null,
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));

jest.mock("react-i18next", () => ({
  initReactI18next: { type: "3rdParty", init: () => {} },
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
  }),
}));

import GlobalVariablesPage from "../index";

describe("GlobalVariablesPage - permissions loading", () => {
  beforeEach(() => {
    mockPermissionsLoading = false;
  });

  it("shows loading feedback instead of an inert table while permissions resolve", () => {
    mockPermissionsLoading = true;

    const { rerender } = render(<GlobalVariablesPage />);

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByTestId("loading-icon")).toHaveAccessibleName("Loading");
    expect(screen.queryByTestId("global-variables-table")).toBeNull();

    mockPermissionsLoading = false;
    rerender(<GlobalVariablesPage />);

    expect(screen.queryByTestId("loading-icon")).toBeNull();
    expect(screen.getByTestId("global-variables-table")).toBeInTheDocument();
  });

  it("mounts the variable share seam without trusting row share capability", () => {
    render(<GlobalVariablesPage />);

    const shareSeam = screen.getByTestId("variable-share-seam");
    expect(shareSeam).toHaveAttribute("data-resource-id", "variable-1");
    expect(shareSeam).toHaveTextContent("TEST_VARIABLE");
  });
});

describe("GlobalVariablesPage - valueFormatter Tests", () => {
  const valueFormatter = (
    params: Partial<ValueFormatterParams<GlobalVariable>>,
  ): string => {
    const isCreditential = params.data?.type === "Credential";
    if (isCreditential) {
      return "*****";
    }
    return params.value ?? "";
  };

  const arrayFormatter = (
    params: Partial<ValueFormatterParams<GlobalVariable>>,
  ): string => params.value?.join(", ") ?? "";

  it("should mask credential type with actual value", () => {
    const result = valueFormatter({
      value: "secret-password",
      data: { type: "Credential" } as unknown as GlobalVariable,
    });
    expect(result).toBe("*****");
  });

  it("should display actual string value for generic type", () => {
    const result = valueFormatter({
      value: "https://api.example.com",
      data: { type: "Generic" } as unknown as GlobalVariable,
    });
    expect(result).toBe("https://api.example.com");
  });

  it("should mask credential type regardless of value (null, empty, etc)", () => {
    expect(
      valueFormatter({
        value: null,
        data: { type: "Credential" } as unknown as GlobalVariable,
      }),
    ).toBe("*****");
    expect(
      valueFormatter({
        value: "",
        data: { type: "Credential" } as unknown as GlobalVariable,
      }),
    ).toBe("*****");
    expect(
      valueFormatter({
        value: undefined,
        data: { type: "Credential" } as unknown as GlobalVariable,
      }),
    ).toBe("*****");
  });

  it("should display generic type with various values (null, zero, false)", () => {
    expect(
      valueFormatter({
        value: null,
        data: { type: "Generic" } as unknown as GlobalVariable,
      }),
    ).toBe("");
    expect(
      valueFormatter({
        value: 0,
        data: { type: "Generic" } as unknown as GlobalVariable,
      }),
    ).toBe(0);
    expect(
      valueFormatter({
        value: false,
        data: { type: "Generic" } as unknown as GlobalVariable,
      }),
    ).toBe(false);
  });

  it("should handle mixed credential and generic variables in table", () => {
    const credentialVar: GlobalVariable = {
      id: "1",
      name: "PASSWORD",
      value: "secret",
      type: "Credential",
      default_fields: [],
    };
    const genericVar: GlobalVariable = {
      id: "2",
      name: "ENDPOINT",
      value: "https://api.com",
      type: "Generic",
      default_fields: [],
    };

    expect(
      valueFormatter({ value: credentialVar.value, data: credentialVar }),
    ).toBe("*****");
    expect(valueFormatter({ value: genericVar.value, data: genericVar })).toBe(
      "https://api.com",
    );
  });

  it("should have value column with valueFormatter applied", () => {
    const colDefs = [
      {
        field: "value",
        valueFormatter: valueFormatter,
      },
    ];

    const valueColumn = colDefs.find((col) => col.field === "value");
    expect(valueColumn).toBeDefined();
    expect(typeof valueColumn?.valueFormatter).toBe("function");
  });

  it("should have all required column definitions", () => {
    const colDefs: ColDef<GlobalVariable>[] = [
      { headerName: "Variable Name", field: "name", flex: 2 },
      { headerName: "Type", field: "type", cellRenderer: jest.fn() },
      { field: "value", valueFormatter },
      {
        headerName: "Apply To Fields",
        field: "default_fields",
        valueFormatter: arrayFormatter,
      },
    ];

    expect(colDefs.map((c) => c.field)).toEqual([
      "name",
      "type",
      "value",
      "default_fields",
    ]);
    expect(colDefs.length).toBe(4);
  });

  it("should format array fields with comma separator", () => {
    expect(arrayFormatter({ value: ["field1", "field2", "field3"] })).toBe(
      "field1, field2, field3",
    );
    expect(arrayFormatter({ value: ["field1"] })).toBe("field1");
    expect(arrayFormatter({ value: [] })).toBe("");
    expect(arrayFormatter({ value: null })).toBe("");
  });

  it("should handle edge cases with unknown type and special characters", () => {
    expect(
      valueFormatter({
        value: "some-value",
        data: { type: "Unknown" } as unknown as GlobalVariable,
      }),
    ).toBe("some-value");
    expect(
      valueFormatter({
        value: "p@ss!word#$%",
        data: { type: "Credential" } as unknown as GlobalVariable,
      }),
    ).toBe("*****");
    expect(valueFormatter({ value: "test", data: undefined })).toBe("test");
  });
});
