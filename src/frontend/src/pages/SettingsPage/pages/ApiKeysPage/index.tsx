import type { SelectionChangedEvent } from "ag-grid-community";
import { useContext, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import Loading from "@/components/ui/loading";
import {
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
  const {
    data: apiKeysData,
    isFetching,
    isLoading,
    refetch,
  } = useGetApiKeysQuery({
    enabled: Boolean(userData),
  });
  const userId = apiKeysData?.user_id ?? "";
  const keysList = useMemo(
    () =>
      apiKeysData?.api_keys.map((apikey) => ({
        ...apikey,
        name: apikey.name && apikey.name !== "" ? apikey.name : "Untitled",
      })) ?? [],
    [apiKeysData],
  );

  async function getApiKeysQuery() {
    await refetch();
  }

  const { mutate } = useDeleteApiKey();

  function handleDeleteApi() {
    for (let i = 0; i < selectedRows.length; i++) {
      mutate(
        { keyId: selectedRows[i] },
        {
          onSuccess: () => {
            getApiKeysQuery();
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

  const columnDefs = getColumnDefs(t);
  const showInitialLoading =
    Boolean(userData) && (isLoading || isFetching) && keysList.length === 0;

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <ApiKeyHeaderComponent
        selectedRows={selectedRows}
        fetchApiKeys={getApiKeysQuery}
        userId={userId}
      />

      <div className="flex h-full w-full flex-col justify-between">
        {showInitialLoading ? (
          <div className="flex h-full min-h-72 w-full items-center justify-center rounded-md border">
            <Loading
              aria-label={t("common.loading", "Loading")}
              className="h-6 w-6 text-primary"
            />
          </div>
        ) : (
          <TableComponent
            key={"apiKeys"}
            tableLabel={t("settings.apiKeysTitle")}
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
        )}
      </div>
    </div>
  );
}
