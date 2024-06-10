import {
  CellEditRequestEvent,
  ColDef,
  ColGroupDef,
  SelectionChangedEvent,
} from "ag-grid-community";
import { useState } from "react";
import TableComponent from "../../../../components/tableComponent";
import { Card, CardContent } from "../../../../components/ui/card";
import useAlertStore from "../../../../stores/alertStore";
import { useMessagesStore } from "../../../../stores/messagesStore";
import useUpdateMessage from "../../../../pages/SettingsPage/pages/messagesPage/hooks/use-updateMessage";
import useRemoveMessages from "../../../../pages/SettingsPage/pages/messagesPage/hooks/use-remove-messages";
import HeaderMessagesComponent from "../../../../pages/SettingsPage/pages/messagesPage/components/headerMessages";
import { Button } from "../../../../components/ui/button";
import ForwardedIconComponent from "../../../../components/genericIconComponent";
import { cn } from "../../../../utils/utils";

export default function SessionView({ rows }: { rows: Array<any> }) {
  const columns = useMessagesStore((state) => state.columns);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const [selectedRows, setSelectedRows] = useState<number[]>([]);

  const { handleRemoveMessages } = useRemoveMessages(
    setSelectedRows,
    setSuccessData,
    setErrorData,
    selectedRows,
  );

  const { handleUpdate } = useUpdateMessage(setSuccessData, setErrorData);

  function handleUpdateMessage(event: CellEditRequestEvent<any, string>) {
    const newValue = event.newValue;
    const field = event.column.getColId();
    const row = event.data;
    const data = {
      ...row,
      [field]: newValue,
    };
    handleUpdate(data);
  }

  return (
    <TableComponent
      key={"sessionView"}
      onDelete={handleRemoveMessages}
      readOnlyEdit
      onCellEditRequest={(event) => {
        handleUpdateMessage(event);
      }}
      editable={["Sender Name", "Message"]}
      overlayNoRowsTemplate="No data available"
      onSelectionChanged={(event: SelectionChangedEvent) => {
        setSelectedRows(event.api.getSelectedRows().map((row) => row.index));
      }}
      rowSelection="multiple"
      suppressRowClickSelection={true}
      pagination={true}
      columnDefs={columns}
      rowData={rows}
    />
  );
}
