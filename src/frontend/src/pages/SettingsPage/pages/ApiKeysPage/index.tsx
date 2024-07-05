import { SelectionChangedEvent } from "ag-grid-community";
import { useContext, useEffect, useRef, useState } from "react";
import TableComponent from "../../../../components/tableComponent";
import { AuthContext } from "../../../../contexts/authContext";
import useAlertStore from "../../../../stores/alertStore";
import ApiKeyHeaderComponent from "./components/ApiKeyHeader";
import { getColumnDefs } from "./helpers/column-defs";
import useApiKeys from "./hooks/use-api-keys";
import useDeleteApiKeys from "./hooks/use-handle-delete-key";

export default function ApiKeysPage() {
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { userData } = useContext(AuthContext);
  const [userId, setUserId] = useState("");
  const keysList = useRef([]);

  useEffect(() => {
    fetchApiKeys();
  }, [userData]);

  const { fetchApiKeys } = useApiKeys(
    userData,
    setLoadingKeys,
    keysList,
    setUserId,
  );

  function resetFilter() {
    fetchApiKeys();
  }

  const { handleDeleteKey } = useDeleteApiKeys(
    selectedRows,
    resetFilter,
    setSuccessData,
    setErrorData,
  );

  const columnDefs = getColumnDefs();

  return (
    <div className="flex h-full w-full flex-col justify-between gap-6">
      <ApiKeyHeaderComponent
        selectedRows={selectedRows}
        fetchApiKeys={fetchApiKeys}
        userId={userId}
      />

      <div className="flex h-full w-full flex-col justify-between">
        <TableComponent
          key={"apiKeys"}
          onDelete={handleDeleteKey}
          overlayNoRowsTemplate="No data available"
          onSelectionChanged={(event: SelectionChangedEvent) => {
            setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
          }}
          rowSelection="multiple"
          suppressRowClickSelection={true}
          pagination={true}
          columnDefs={columnDefs}
          rowData={keysList.current}
        />
      </div>
    </div>
  );
}
