import type { SelectionChangedEvent } from "ag-grid-community";
import { useContext, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
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
  const [envIpRestrictionEnabled, setEnvIpRestrictionEnabled] = useState(false);
  const [envIpRestriction, setEnvIpRestriction] = useState<string | null>(null);
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
      setEnvIpRestrictionEnabled(Boolean(data["env_ip_restriction_enabled"]));
      setEnvIpRestriction(data["env_ip_restriction"] ?? null);
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

  const columnDefs = getColumnDefs({
    hideIpRestriction: envIpRestrictionEnabled,
  });

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <ApiKeyHeaderComponent
        selectedRows={selectedRows}
        fetchApiKeys={getApiKeysQuery}
        userId={userId}
        envIpRestrictionEnabled={envIpRestrictionEnabled}
      />

      {envIpRestrictionEnabled && (
        <div
          className="flex items-start gap-3 rounded-md border border-accent-amber-foreground bg-accent-amber/20 p-3"
          data-testid="env_ip_restriction_banner"
        >
          <ForwardedIconComponent
            name="ShieldCheck"
            className="mt-0.5 h-5 w-5 flex-shrink-0 text-accent-amber-foreground"
          />
          <div className="flex flex-col gap-1 text-sm">
            <p className="font-medium text-accent-amber-foreground">
              Global IP restriction is active
            </p>
            <p className="text-muted-foreground">
              The{" "}
              <code className="rounded bg-muted px-1 font-mono text-xs">
                LANGFLOW_API_IP_RESTRICTION
              </code>{" "}
              environment variable is set. All API key requests must originate
              from the allow-listed IPs; per-key IP restrictions are ignored.
            </p>
            {envIpRestriction && (
              <p className="text-muted-foreground">
                Allow-list:{" "}
                <code className="rounded bg-muted px-1 font-mono text-xs">
                  {envIpRestriction}
                </code>
              </p>
            )}
          </div>
        </div>
      )}

      <div className="flex h-full w-full flex-col justify-between">
        <TableComponent
          key={envIpRestrictionEnabled ? "apiKeys-env" : "apiKeys"}
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
