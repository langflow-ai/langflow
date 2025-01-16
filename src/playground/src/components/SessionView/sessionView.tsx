/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable @typescript-eslint/no-explicit-any */
import Loading from "@/components/ui/loading";
import {
  useDeleteMessages,
  useUpdateMessage,
} from "@/controllers/API/queries/messages";
import { useIsFetching } from "@tanstack/react-query";
import { NewValueParams, SelectionChangedEvent } from "ag-grid-community";
import cloneDeep from "lodash/cloneDeep";
import { useMemo, useState } from "react";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import { useMessagesStore } from "src/stores/messageStore";
import { extractColumnsFromRows, messagesSorter } from "@/utils/utils";
import { usePlaygroundStore } from "src/stores/playgroundStore";

export default function SessionView({
  session,
  id,
}: {
  session?: string;
  id?: string;
}) {
  const messages = useMessagesStore((state) => state.messages);
  const onMessageDelete = usePlaygroundStore((state) => state.onMessageDelete);
  const onMessageDeleteError = usePlaygroundStore((state) => state.onMessageDeleteError);
  const updateMessage = useMessagesStore((state) => state.updateMessage);
  const deleteMessagesStore = useMessagesStore((state) => state.removeMessages);
  const onMessageUpdate = usePlaygroundStore((state) => state.onMessageUpdate);
  const onMessageUpdateError = usePlaygroundStore((state) => state.onMessageUpdateError);
  const columns = extractColumnsFromRows(messages, "intersection");
  const isFetching = useIsFetching({
    queryKey: ["useGetMessagesQuery"],
    exact: false,
  });
  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  const { mutate: deleteMessages } = useDeleteMessages({
    onSuccess: () => {
      deleteMessagesStore(selectedRows);
      setSelectedRows([]);
      onMessageDelete?.("Messages deleted successfully.");
    },
    onError: () => {
      onMessageDeleteError?.("Error deleting messages.");
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
          onMessageUpdate?.("Messages updated successfully.");
        },
        onError: () => {
          onMessageUpdateError?.("Error updating messages.");
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

  return isFetching > 0 ? (
    <div className="flex h-full w-full items-center justify-center align-middle">
      <Loading></Loading>
    </div>
  ) : (
    <TableComponent
      key={"sessionView"}
      onDelete={handleRemoveMessages}
      readOnlyEdit
      editable={[
        { field: "text", onUpdate: handleUpdateMessage, editableCell: false },
      ]}
      overlayNoRowsTemplate="No data available"
      // @ts-expect-error
      onSelectionChanged={(event: SelectionChangedEvent) => {
        setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
        return;
      }}
      rowSelection="multiple"
      suppressRowClickSelection={true}
      pagination={true}
      columnDefs={columns.sort(messagesSorter)}
      rowData={filteredMessages}
    />
  );
}
