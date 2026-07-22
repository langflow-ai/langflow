import type {
  CellKeyDownEvent,
  ColDef,
  RowClickedEvent,
  SelectionChangedEvent,
  SuppressKeyboardEventParams,
  ValueFormatterParams,
} from "ag-grid-community";
import type { AgGridReact } from "ag-grid-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import Dropdown from "@/components/core/dropdownComponent";
import GlobalVariableModal from "@/components/core/GlobalVariableModal/GlobalVariableModal";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { PROVIDER_VARIABLE_MAPPING } from "@/constants/providerConstants";
import {
  PermissionsProvider,
  usePermissions,
} from "@/contexts/permissionsContext";
import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
} from "@/controllers/API/queries/variables";
import CustomVariableShareAction from "@/customization/components/custom-variable-share-action";
import type { GlobalVariable } from "@/types/global_variables";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/common/genericIconComponent";
import { Badge } from "../../../../components/ui/badge";
import { Button } from "../../../../components/ui/button";
import useAlertStore from "../../../../stores/alertStore";
import {
  authorizedVariableIds,
  canMutateVariable,
  canShareVariable,
  formatVariableValue,
} from "./variableAccess";

/** Let onCellKeyDown own Enter/Space so AG Grid does not also toggle selection. */
function suppressRowActionKeys(params: SuppressKeyboardEventParams) {
  const key = params.event.key;
  return key === "Enter" || key === " " || key === "Spacebar";
}

type FocusedCell = { rowIndex: number; colId: string };

export default function GlobalVariablesPage() {
  const { data: globalVariables } = useGetGlobalVariables();
  const resourceIds = useMemo(
    () => globalVariables?.map((variable) => variable.id) ?? [],
    [globalVariables],
  );

  return (
    <PermissionsProvider
      resourceType="variable"
      resourceIds={resourceIds}
      actions={["read", "write", "delete"]}
    >
      <GlobalVariablesPageContent globalVariables={globalVariables} />
    </PermissionsProvider>
  );
}

function GlobalVariablesPageContent({
  globalVariables,
}: {
  globalVariables: GlobalVariable[] | undefined;
}) {
  const { t } = useTranslation();
  const {
    can,
    isLoading: permissionsLoading,
    isError: permissionsError,
    permissions,
  } = usePermissions();
  const permissionState = useMemo(
    () => ({
      isLoading: permissionsLoading,
      isError: permissionsError,
      permissions,
    }),
    [permissions, permissionsError, permissionsLoading],
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [openModal, setOpenModal] = useState(false);
  const initialData = useRef<GlobalVariable | undefined>(undefined);
  const gridRef = useRef<AgGridReact>(null);
  const lastFocusedCell = useRef<FocusedCell | null>(null);
  const BadgeRenderer = (props) => {
    return props.value !== "" ? (
      <div>
        <Badge variant="outline" size="md" className="font-normal">
          {props.value}
        </Badge>
      </div>
    ) : (
      <div></div>
    );
  };

  const DropdownEditor = ({ options, value, onValueChange }) => {
    return (
      <Dropdown options={options} value={value} onSelect={onValueChange}>
        <div className="-mt-1.5 w-full"></div>
      </Dropdown>
    );
  };
  // Column Definitions: Defines the columns to be displayed.
  const colDefs: ColDef[] = [
    {
      headerName: t("globalVars.columnVariableName"),
      field: "name",
      flex: 2,
      suppressKeyboardEvent: suppressRowActionKeys,
    }, //This column will be twice as wide as the others
    {
      headerName: t("globalVars.columnType"),
      field: "type",
      cellRenderer: BadgeRenderer,
      cellEditor: DropdownEditor,
      cellEditorParams: {
        options: ["Generic", "Credential"],
      },
      flex: 1,
      suppressKeyboardEvent: suppressRowActionKeys,
    },
    {
      field: "value",
      valueFormatter: (params: ValueFormatterParams<GlobalVariable>) => {
        return formatVariableValue(
          params.data,
          params.value,
          t("globalVars.sharedValueHidden", "Shared value hidden"),
        );
      },
      suppressKeyboardEvent: suppressRowActionKeys,
    },
    {
      headerName: t("globalVars.columnApplyToFields"),
      field: "default_fields",
      valueFormatter: (params) => {
        return params.value?.join(", ") ?? "";
      },
      flex: 1,
      resizable: false,
      suppressKeyboardEvent: suppressRowActionKeys,
    },
    {
      headerName: t("globalVars.columnAccess", "Access"),
      colId: "access",
      cellRenderer: ({ data }: { data?: GlobalVariable }) =>
        data?.is_owner === false ? (
          <Badge variant="secondary" size="md" className="font-normal">
            {t("globalVars.shared", "Shared")}
          </Badge>
        ) : null,
      flex: 1,
      suppressKeyboardEvent: suppressRowActionKeys,
    },
    {
      headerName: t("globalVars.columnActions", "Actions"),
      colId: "actions",
      cellRenderer: ({ data }: { data?: GlobalVariable }) => {
        if (!data || !canShareVariable(data)) return null;
        return (
          <CustomVariableShareAction
            resourceId={data.id}
            resourceName={data.name}
          />
        );
      },
      flex: 1,
      sortable: false,
      filter: false,
      suppressKeyboardEvent: suppressRowActionKeys,
    },
  ];

  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  const { mutate: mutateDeleteGlobalVariable } = useDeleteGlobalVariables();

  // Get list of provider variable names to identify provider credentials
  const providerVariableNames = useMemo(
    () => new Set(Object.values(PROVIDER_VARIABLE_MAPPING)),
    [],
  );

  // Filter out invalid provider credentials
  const validGlobalVariables = useMemo(() => {
    if (!globalVariables) return [];

    return globalVariables.filter((variable) => {
      // Check if this is a provider credential variable
      const isProviderCredential =
        variable.type === "Credential" &&
        providerVariableNames.has(variable.name);

      if (isProviderCredential) {
        // If validation failed (is_valid === false), filter it out
        if (variable.is_valid === false) {
          return false; // Filter out invalid provider credentials
        }
      }

      return true; // Keep all other variables and valid provider credentials
    });
  }, [globalVariables, providerVariableNames]);

  // Show validation errors for invalid provider credentials (only once when detected)
  useEffect(() => {
    if (!globalVariables) return;

    const invalidProviderVars = globalVariables.filter(
      (variable) =>
        variable.type === "Credential" &&
        providerVariableNames.has(variable.name) &&
        variable.is_valid === false,
    );

    if (invalidProviderVars.length > 0) {
      const errorMessages = invalidProviderVars.map(
        (variable) =>
          `${variable.name}: ${variable.validation_error || "Invalid API key"}`,
      );
      setErrorData({
        title: t("globalVars.invalidCredentialsTitle"),
        list: [
          t("globalVars.invalidCredentialsHidden", {
            count: invalidProviderVars.length,
          }),
          ...errorMessages,
        ],
      });
    }
  }, [globalVariables, providerVariableNames, setErrorData]);

  const revalidateSelectedRows = useCallback(
    (ids: readonly string[]) =>
      authorizedVariableIds(
        ids,
        validGlobalVariables,
        "delete",
        permissionState,
        can,
      ),
    [can, permissionState, validGlobalVariables],
  );

  const deselectUnauthorizedRows = useCallback(
    (authorizedIds: readonly string[]) => {
      const authorized = new Set(authorizedIds);
      const api = gridRef.current?.api;
      if (!api || api.isDestroyed()) return;
      api.forEachNode((node) => {
        const id = node.data?.id;
        if (node.isSelected() && (!id || !authorized.has(id)))
          node.setSelected(false);
      });
    },
    [],
  );

  useEffect(() => {
    if (selectedRows.length === 0) return;
    const authorizedIds = revalidateSelectedRows(selectedRows);
    if (
      authorizedIds.length === selectedRows.length &&
      authorizedIds.every((id, index) => id === selectedRows[index])
    )
      return;

    deselectUnauthorizedRows(authorizedIds);
    setSelectedRows(authorizedIds);
  }, [deselectUnauthorizedRows, revalidateSelectedRows, selectedRows]);

  function removeVariables() {
    const authorizedIds = revalidateSelectedRows(selectedRows);
    if (authorizedIds.length !== selectedRows.length) {
      deselectUnauthorizedRows(authorizedIds);
      setSelectedRows(authorizedIds);
    }

    authorizedIds.forEach((id) => {
      const row = validGlobalVariables.find((variable) => variable.id === id);
      mutateDeleteGlobalVariable(
        { id },
        {
          onError: () => {
            setErrorData({
              title: t("globalVars.errorDeletingVariable"),
              list: [
                t("globalVars.errorIdNotFound", { name: row?.name ?? id }),
              ],
            });
          },
        },
      );
    });
  }

  function rememberFocusedCell(
    rowIndex: number | null | undefined,
    colId?: string,
  ) {
    if (rowIndex == null) return;
    lastFocusedCell.current = {
      rowIndex,
      colId: colId || "name",
    };
  }

  const restoreFocusedCell = useCallback(() => {
    const cell = lastFocusedCell.current;
    const api = gridRef.current?.api;
    if (!cell || !api || api.isDestroyed()) return;

    const restore = () => {
      api.ensureIndexVisible(cell.rowIndex);
      api.setFocusedCell(cell.rowIndex, cell.colId);
      const focused = document.querySelector<HTMLElement>(
        `.ag-center-cols-container .ag-row[row-index="${cell.rowIndex}"] [role="gridcell"][col-id="${cell.colId}"]`,
      );
      focused?.focus({ preventScroll: true });
    };

    // Outlast Radix dialog focus cleanup (WCAG 2.4.3).
    requestAnimationFrame(() => {
      restore();
      requestAnimationFrame(() => {
        restore();
        requestAnimationFrame(restore);
      });
    });
  }, []);

  const handleEditModalOpenChange = useCallback(
    (open: boolean | ((prev?: boolean) => boolean)) => {
      setOpenModal((prev) => {
        const next = typeof open === "function" ? open(prev) : open;
        if (!next) {
          queueMicrotask(() => restoreFocusedCell());
        }
        return next;
      });
    },
    [restoreFocusedCell],
  );

  function updateVariables(event: RowClickedEvent<GlobalVariable>) {
    if (!canMutateVariable(event.data, "write", permissionState, can)) return;
    rememberFocusedCell(event.rowIndex, "name");
    initialData.current = event.data;
    setOpenModal(true);
  }

  function handleCellKeyDown(event: CellKeyDownEvent<GlobalVariable>) {
    const keyboardEvent = event.event as KeyboardEvent | undefined;
    if (!keyboardEvent) return;

    // Let AG Grid / the checkbox handle Space when focus is already on it.
    if (
      (keyboardEvent.target as HTMLElement | null)?.closest(
        ".ag-selection-checkbox",
      )
    ) {
      return;
    }

    if (keyboardEvent.key === "Enter") {
      keyboardEvent.preventDefault();
      keyboardEvent.stopPropagation();
      if (event.data) {
        if (!canMutateVariable(event.data, "write", permissionState, can))
          return;
        rememberFocusedCell(event.rowIndex, event.column?.getColId());
        initialData.current = event.data;
        setOpenModal(true);
      }
      return;
    }

    // Space toggles row selection (checkbox) without opening the edit modal.
    // Scoped to this page via onCellKeyDown — other tables are unchanged.
    if (keyboardEvent.key === " " || keyboardEvent.key === "Spacebar") {
      if (!canMutateVariable(event.data, "delete", permissionState, can))
        return;
      keyboardEvent.preventDefault();
      keyboardEvent.stopPropagation();
      const select = !event.node.isSelected();
      event.node.setSelected(select, false);
      // TableOptions.hasSelection is read at render time from the grid API, so
      // sync React state so the delete control updates immediately.
      setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
    }
  }

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex min-w-0 flex-1 flex-col">
          <h2
            className="flex items-center text-lg font-semibold tracking-tight"
            data-testid="settings_menu_header"
          >
            {t("globalVars.pageTitle")}
            <ForwardedIconComponent
              name="Globe"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("globalVars.pageDescription")}
          </p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2 pr-1">
          <GlobalVariableModal asChild>
            <Button data-testid="api-key-button-store" variant="primary">
              <IconComponent name="Plus" className="w-4" />
              {t("globalVars.addNew")}
            </Button>
          </GlobalVariableModal>
        </div>
      </div>

      <div className="flex h-full w-full flex-col justify-between">
        <TableComponent
          ref={gridRef}
          key={"globalVariables"}
          overlayNoRowsTemplate={t("globalVars.noDataAvailable")}
          onSelectionChanged={(event: SelectionChangedEvent) => {
            setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
          }}
          rowSelection="multiple"
          isRowSelectable={(row) =>
            Boolean(canMutateVariable(row.data, "delete", permissionState, can))
          }
          onRowClicked={updateVariables}
          onCellKeyDown={handleCellKeyDown}
          onCellFocused={(event) => {
            if (event.rowIndex == null) return;
            const colId =
              typeof event.column === "string"
                ? event.column
                : event.column?.getColId();
            rememberFocusedCell(event.rowIndex, colId);
          }}
          suppressRowClickSelection={true}
          pagination={true}
          columnDefs={colDefs}
          rowData={validGlobalVariables ?? []}
          onDelete={removeVariables}
        />
        {initialData.current && (
          <GlobalVariableModal
            key={initialData.current.id}
            initialData={initialData.current}
            open={openModal}
            setOpen={handleEditModalOpenChange}
          />
        )}
      </div>
    </div>
  );
}
