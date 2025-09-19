import { useIsFetching } from "@tanstack/react-query";
import type { NewValueParams, SelectionChangedEvent } from "ag-grid-community";
import cloneDeep from "lodash/cloneDeep";
import { useMemo, useState } from "react";
import Loading from "@/components/ui/loading";
import {
  useDeleteMessages,
  useUpdateMessage,
} from "@/controllers/API/queries/messages";
import useFlowStore from "@/stores/flowStore";
import TableComponent from "../../../components/core/parameterRenderComponent/components/tableComponent";
import useAlertStore from "../../../stores/alertStore";
import { useMessagesStore } from "../../../stores/messagesStore";
import { extractColumnsFromRows, messagesSorter } from "../../../utils/utils";

export default function SessionView({
  session,
  id,
}: {
  session?: string;
  id?: string;
}) {
  const messages = useMessagesStore((state) => state.messages);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const updateMessage = useMessagesStore((state) => state.updateMessage);
  const deleteMessagesStore = useMessagesStore((state) => state.removeMessages);
  const columns = extractColumnsFromRows(messages, "intersection");
  const playgroundPage = useFlowStore((state) => state.playgroundPage);
  const isFetching = useIsFetching({
    queryKey: ["useGetMessagesQuery"],
    exact: false,
  });
  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  const { mutate: deleteMessages } = useDeleteMessages({
    onSuccess: () => {
      deleteMessagesStore(selectedRows);
      setSelectedRows([]);
      setSuccessData({
        title: "Messages deleted successfully.",
      });
    },
    onError: () => {
      setErrorData({
        title: "Error deleting messages.",
      });
    },
  });

  const { mutate: updateMessageMutation } = useUpdateMessage();

  function handleUpdateMessage(event: NewValueParams<any, string>) {
    const newValue = event.newValue;
    const field = event.column.getColId();
    const row = cloneDeep(event.data);
    const data = {
      ...row,
      [field]: newValue,
    };
    updateMessageMutation(
      { message: data },
      {
        onSuccess: () => {
          updateMessage(data);
          // Set success message
          setSuccessData({
            title: "Messages updated successfully.",
          });
        },
        onError: () => {
          setErrorData({
            title: "Error updating messages.",
          });
          event.data[field] = event.oldValue;
          event.api.refreshCells();
        },
      },
    );
  }

  const filteredMessages = useMemo(() => {
    let filteredMessages = session
      ? messages.filter((message) => message.session_id === session)
      : messages;
    filteredMessages = id
      ? filteredMessages.filter((message) => message.flow_id === id)
      : filteredMessages;
    return filteredMessages;
  }, [session, id, messages]);

  function handleRemoveMessages() {
    deleteMessages({ ids: selectedRows });
  }

  const editable = useMemo(() => {
    return playgroundPage
      ? false
      : [{ field: "text", onUpdate: handleUpdateMessage, editableCell: false }];
  }, [handleUpdateMessage]);

  return isFetching > 0 ? (
    <div className="flex h-full w-full items-center justify-center align-middle">
      <Loading></Loading>
    </div>
  ) : (
    <TableComponent
      key={"sessionView"}
      onDelete={playgroundPage ? undefined : handleRemoveMessages}
      readOnlyEdit
      editable={editable}
      overlayNoRowsTemplate="No data available"
      onSelectionChanged={(event: SelectionChangedEvent) => {
        setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
      }}
      rowSelection={playgroundPage ? undefined : "multiple"}
      suppressRowClickSelection={true}
      pagination={true}
      columnDefs={columns.sort(messagesSorter)}
      rowData={filteredMessages}
    />
  );
}
