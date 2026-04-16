import type { SelectionChangedEvent } from "ag-grid-community";
import { useContext, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  type IApiKeysDataArray,
  useDeleteApiKey,
  useGetApiKeysQuery,
} from "@/controllers/API/queries/api-keys";
import TableComponent from "../../../../components/core/parameterRenderComponent/components/tableComponent";
import { AuthContext } from "../../../../contexts/authContext";
import useAlertStore from "../../../../stores/alertStore";
import ApiKeyHeaderComponent from "./components/ApiKeyHeader";
import { getColumnDefs } from "./helpers/column-defs";

export default function ApiKeysPage() {
  const { t } = useTranslation();
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData } = useContext(AuthContext);
  const [userId, setUserId] = useState("");
  const [keysList, setKeysList] = useState<IApiKeysDataArray[]>([]);
  const { refetch } = useGetApiKeysQuery();

  async function getApiKeysQuery() {
    const { data } = await refetch();
    if (data !== undefined) {
      const updatedKeysList = data["api_keys"].map((apikey) => ({
        ...apikey,
        name: apikey.name && apikey.name !== "" ? apikey.name : "Untitled",
        last_used_at: apikey.last_used_at ?? "Never",
      }));
      setKeysList(updatedKeysList);
      setUserId(data["user_id"]);
    }
  }

  useEffect(() => {
    if (userData) {
      getApiKeysQuery();
    }
  }, [userData]);

  function resetFilter() {
    getApiKeysQuery();
  }

  const { mutate } = useDeleteApiKey();

  function handleDeleteApi() {
    for (let i = 0; i < selectedRows.length; i++) {
      mutate(
        { keyId: selectedRows[i] },
        {
          onSuccess: () => {
            resetFilter();
            setSuccessData({
              title:
                selectedRows.length === 1
                  ? t("success.keyDeleted")
                  : t("success.keysDeleted"),
            });
          },
          onError: (error) => {
            setErrorData({
              title:
                selectedRows.length === 1
                  ? t("errors.deleteKey")
                  : t("errors.deleteKeys"),
              list: [error?.response?.data?.detail],
            });
          },
        },
      );
    }
  }

  const columnDefs = getColumnDefs();

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <ApiKeyHeaderComponent
        selectedRows={selectedRows}
        fetchApiKeys={getApiKeysQuery}
        userId={userId}
      />

      <div className="flex h-full w-full flex-col justify-between">
        <TableComponent
          key={"apiKeys"}
          onDelete={handleDeleteApi}
          overlayNoRowsTemplate={t("settings.noDataAvailable")}
          onSelectionChanged={(event: SelectionChangedEvent) => {
            setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
          }}
          rowSelection="multiple"
          suppressRowClickSelection={true}
          pagination={true}
          columnDefs={columnDefs}
          rowData={keysList}
        />
      </div>
    </div>
  );
}
