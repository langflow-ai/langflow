import IconComponent from "../../../../components/genericIconComponent";
import { Button } from "../../../../components/ui/button";

import { ColDef, ColGroupDef, SelectionChangedEvent } from "ag-grid-community";
import { useContext, useEffect, useRef, useState } from "react";
import AddNewVariableButton from "../../../../components/addNewVariableButtonComponent/addNewVariableButton";
import Dropdown from "../../../../components/dropdownComponent";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import TableComponent from "../../../../components/tableComponent";
import { Badge } from "../../../../components/ui/badge";
import { Card, CardContent } from "../../../../components/ui/card";
import {
  deleteApiKey,
  deleteGlobalVariable,
  getApiKey,
} from "../../../../controllers/API";
import useAlertStore from "../../../../stores/alertStore";
import { useGlobalVariablesStore } from "../../../../stores/globalVariablesStore/globalVariables";
import { cn } from "../../../../utils/utils";
import {
  API_PAGE_PARAGRAPH,
  LAST_USED_SPAN_1,
  LAST_USED_SPAN_2,
} from "../../../../constants/constants";
import TableAutoCellRender from "../../../../components/tableAutoCellRender";
import {
  DEL_KEY_SUCCESS_ALERT,
  DEL_KEY_ERROR_ALERT,
  DEL_KEY_SUCCESS_ALERT_PLURAL,
  DEL_KEY_ERROR_ALERT_PLURAL,
} from "../../../../constants/alerts_constants";
import { AuthContext } from "../../../../contexts/authContext";
import { ApiKey } from "../../../../types/components";
import SecretKeyModal from "../../../../modals/secretKeyModal";

export default function ApiKeysPage() {
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData } = useContext(AuthContext);
  const [userId, setUserId] = useState("");
  const keysList = useRef([]);

  useEffect(() => {
    getKeys();
  }, [userData]);

  function getKeys() {
    setLoadingKeys(true);
    if (userData) {
      getApiKey()
        .then((keys: [ApiKey]) => {
          keysList.current = keys["api_keys"].map((apikey: ApiKey) => ({
            ...apikey,
            name: apikey.name && apikey.name !== "" ? apikey.name : "Untitled",
            last_used_at: apikey.last_used_at ?? "Never",
          }));
          setUserId(keys["user_id"]);
          setLoadingKeys(false);
        })
        .catch((error) => {
          setLoadingKeys(false);
        });
    }
  }

  function resetFilter() {
    getKeys();
  }

  function handleDeleteKey() {
    Promise.all(selectedRows.map((selectedRow) => deleteApiKey(selectedRow)))
      .then((res) => {
        resetFilter();
        setSuccessData({
          title:
            selectedRows.length === 1
              ? DEL_KEY_SUCCESS_ALERT
              : DEL_KEY_SUCCESS_ALERT_PLURAL,
        });
      })
      .catch((error) => {
        setErrorData({
          title:
            selectedRows.length === 1
              ? DEL_KEY_ERROR_ALERT
              : DEL_KEY_ERROR_ALERT_PLURAL,
          list: [error["response"]["data"]["detail"]],
        });
      });
  }

  function lastUsedMessage() {
    return (
      <div className="text-xs">
        <span>
          {LAST_USED_SPAN_1}
          <br></br> {LAST_USED_SPAN_2}
        </span>
      </div>
    );
  }

  const columnDefs = [
    {
      headerCheckboxSelection: true,
      checkboxSelection: true,
      showDisabledCheckboxes: true,
      headerName: "Name",
      field: "name",
      cellRenderer: TableAutoCellRender,
      flex: 2,
    },
    {
      headerName: "Key",
      field: "api_key",
      cellRenderer: TableAutoCellRender,
      flex: 1,
    },
    {
      headerName: "Created",
      field: "created_at",
      cellRenderer: TableAutoCellRender,
      flex: 1,
    },
    {
      headerName: "Last Used",
      field: "last_used_at",
      cellRenderer: TableAutoCellRender,
      flex: 1,
    },
    {
      headerName: "Total Uses",
      field: "total_uses",
      cellRenderer: TableAutoCellRender,
      flex: 1,
      resizable: false,
    },
  ];

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            API Keys
            <ForwardedIconComponent
              name="Key"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">{API_PAGE_PARAGRAPH}</p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <Button
            data-testid="api-key-button-store"
            variant="primary"
            className="group px-2"
            disabled={selectedRows.length === 0}
            onClick={handleDeleteKey}
          >
            <IconComponent
              name="Trash2"
              className={cn(
                "h-5 w-5 text-destructive group-disabled:text-primary",
              )}
            />
          </Button>
          <SecretKeyModal data={userId} onCloseModal={getKeys}>
            <Button data-testid="api-key-button-store" variant="primary">
              <IconComponent name="Plus" className="mr-2 w-4" />
              Add New
            </Button>
          </SecretKeyModal>
        </div>
      </div>

      <div className="flex h-full w-full flex-col justify-between">
        <Card x-chunk="dashboard-04-chunk-2" className="h-full pt-4">
          <CardContent className="h-full">
            <TableComponent
              overlayNoRowsTemplate="No data available"
              onSelectionChanged={(event: SelectionChangedEvent) => {
                setSelectedRows(
                  event.api.getSelectedRows().map((row) => row.id),
                );
              }}
              rowSelection="multiple"
              suppressRowClickSelection={true}
              pagination={true}
              columnDefs={columnDefs}
              rowData={keysList.current}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
