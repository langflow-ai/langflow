import { useIsFetching } from "@tanstack/react-query";
import type { NewValueParams, SelectionChangedEvent } from "ag-grid-community";
import cloneDeep from "lodash/cloneDeep";
import { useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import TableComponent from "@/components/core/parameterRenderComponent/components/tableComponent";
import Loading from "@/components/ui/loading";
import {
  useDeleteMessages,
  useGetMessagesQuery,
  useUpdateMessage,
} from "@/controllers/API/queries/messages";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { extractColumnsFromRows, messagesSorter } from "@/utils/utils";

interface MessagesMainContentProps {
  selectedSessionId?: string | null;
}

/**
 * Main content area for messages - replaces the canvas when messages section is active
 * Shows a table view of messages filtered by the selected session
 */
export default function MessagesMainContent({
  selectedSessionId,
}: MessagesMainContentProps) {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const messages = useMessagesStore((state) => state.messages);
  const updateMessage = useMessagesStore((state) => state.updateMessage);
  const deleteMessagesStore = useMessagesStore((state) => state.removeMessages);
  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  // Fetch messages for the current flow
  const { isLoading } = useGetMessagesQuery(
    { id: currentFlowId ?? undefined, mode: "union" },
    { enabled: !!currentFlowId },
  );

  const isFetching = useIsFetching({
    queryKey: ["useGetMessagesQuery"],
    exact: false,
  });

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
          setSuccessData({
            title: "Message updated successfully.",
          });
        },
        onError: () => {
          setErrorData({
            title: "Error updating message.",
          });
          event.data[field] = event.oldValue;
          event.api.refreshCells();
        },
      },
    );
  }

  // Filter messages by session
  const filteredMessages = useMemo(() => {
    let filtered = messages;

    // Filter by flow_id
    if (currentFlowId) {
      filtered = filtered.filter((message) => message.flow_id === currentFlowId);
    }

    // Filter by session_id if selected
    if (selectedSessionId !== null && selectedSessionId !== undefined) {
      filtered = filtered.filter(
        (message) => (message.session_id || "") === selectedSessionId,
      );
    }

    return filtered;
  }, [messages, currentFlowId, selectedSessionId]);

  const columns = useMemo(() => {
    return extractColumnsFromRows(filteredMessages, "intersection");
  }, [filteredMessages]);

  function handleRemoveMessages() {
    deleteMessages({ ids: selectedRows });
  }

  const editable = useMemo(() => {
    return [{ field: "text", onUpdate: handleUpdateMessage, editableCell: false }];
  }, []);

  const sessionLabel = selectedSessionId
    ? selectedSessionId.length > 30
      ? `${selectedSessionId.slice(0, 30)}...`
      : selectedSessionId
    : "All Sessions";

  return (
    <div className="flex h-full w-full flex-col bg-background">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-2">
        <IconComponent
          name="MessagesSquare"
          className="h-4 w-4 text-muted-foreground"
        />
        <span className="text-sm font-medium">Messages</span>
        <span className="text-xs text-muted-foreground">
          {sessionLabel} · {filteredMessages.length} message{filteredMessages.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {isLoading || isFetching > 0 ? (
          <div className="flex h-full w-full items-center justify-center">
            <Loading size={64} className="text-primary" />
          </div>
        ) : filteredMessages.length === 0 ? (
          <div className="flex h-full w-full flex-col items-center justify-center text-center">
            <IconComponent
              name="MessagesSquare"
              className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
            />
            <p className="text-sm text-muted-foreground">No messages found</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {selectedSessionId
                ? "This session has no messages"
                : "Run your flow to see messages here"}
            </p>
          </div>
        ) : (
          <TableComponent
            key="messagesView"
            onDelete={handleRemoveMessages}
            readOnlyEdit
            editable={editable}
            overlayNoRowsTemplate="No data available"
            onSelectionChanged={(event: SelectionChangedEvent) => {
              setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
            }}
            rowSelection="multiple"
            suppressRowClickSelection={true}
            pagination={true}
            columnDefs={columns.sort(messagesSorter)}
            rowData={filteredMessages}
          />
        )}
      </div>
    </div>
  );
}
