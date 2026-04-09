import type {
  ColDef,
  RowClickedEvent,
  SelectionChangedEvent,
  ValueFormatterParams,
} from "ag-grid-community";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import Dropdown from "@/components/core/dropdownComponent";
import GlobalVariableModal from "@/components/core/GlobalVariableModal/GlobalVariableModal";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { PROVIDER_VARIABLE_MAPPING } from "@/constants/providerConstants";
import {
  useDeleteGlobalVariables,
  useGetGlobalVariables,
} from "@/controllers/API/queries/variables";
import type { GlobalVariable } from "@/types/global_variables";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/common/genericIconComponent";
import { Badge } from "../../../../components/ui/badge";
import { Button } from "../../../../components/ui/button";
import useAlertStore from "../../../../stores/alertStore";

export default function GlobalVariablesPage() {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [openModal, setOpenModal] = useState(false);
  const initialData = useRef<GlobalVariable | undefined>(undefined);
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
    },
    {
      field: "value",
      valueFormatter: (params: ValueFormatterParams<GlobalVariable>) => {
        const isCreditential = params.data?.type === "Credential";

        if (isCreditential) {
          return "*****";
        }
        return params.value ?? "";
      },
    },
    {
      headerName: t("globalVars.columnApplyToFields"),
      field: "default_fields",
      valueFormatter: (params) => {
        return params.value?.join(", ") ?? "";
      },
      flex: 1,
      resizable: false,
    },
  ];

  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  const { data: globalVariables } = useGetGlobalVariables();
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

  async function removeVariables() {
    selectedRows.map(async (row) => {
      const id = globalVariables?.find((variable) => variable.name === row)?.id;
      mutateDeleteGlobalVariable(
        { id },
        {
          onError: () => {
            setErrorData({
              title: t("globalVars.errorDeletingVariable"),
              list: [t("globalVars.errorIdNotFound", { name: row })],
            });
          },
        },
      );
    });
  }

  function updateVariables(event: RowClickedEvent<GlobalVariable>) {
    initialData.current = event.data;
    setOpenModal(true);
  }

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <div className="flex w-full items-start justify-between gap-6">
        <div className="flex w-full flex-col">
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
        <div className="flex flex-shrink-0 items-center gap-2">
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
          key={"globalVariables"}
          overlayNoRowsTemplate={t("globalVars.noDataAvailable")}
          onSelectionChanged={(event: SelectionChangedEvent) => {
            setSelectedRows(event.api.getSelectedRows().map((row) => row.name));
          }}
          rowSelection="multiple"
          onRowClicked={updateVariables}
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
            setOpen={setOpenModal}
          />
        )}
      </div>
    </div>
  );
}
