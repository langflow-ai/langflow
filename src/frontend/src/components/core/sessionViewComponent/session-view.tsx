import { useIsFetching } from "@tanstack/react-query";
import type { NewValueParams, SelectionChangedEvent } from "ag-grid-community";
import cloneDeep from "lodash/cloneDeep";
import { useMemo, useState } from "react";
import Loading from "@/components/ui/loading";
import {
  useDeleteMessages,
  useGetMessagesQuery,
  useUpdateMessage,
} from "@/controllers/API/queries/messages";
import useFlowStore from "@/stores/flowStore";
import useAlertStore from "../../../stores/alertStore";
import { extractColumnsFromRows, messagesSorter } from "../../../utils/utils";
import TableComponent from "../parameterRenderComponent/components/tableComponent";

export default function SessionView({
  sessionId,
  flowId,
}: {
  sessionId?: string;
  flowId?: string;
}) {
  const { data: messages = [] } = useGetMessagesQuery({
    id: flowId,
    session_id: sessionId,
  });
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const columns = extractColumnsFromRows(messages, "intersection");
  const playgroundPage = useFlowStore((state) => state.playgroundPage);
  const isFetching = useIsFetching({
    queryKey: ["useGetMessagesQuery"],
    exact: false,
  });
  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  const { mutate: deleteMessages } = useDeleteMessages(
    {
      flowId: flowId ?? "",
      sessionId: sessionId ?? "",
    },
    {
      onSuccess: () => {
        if (!sessionId || !flowId) {
          return;
        }
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
    },
  );

  const { mutate: updateMessageMutation } = useUpdateMessage({
    flowId: flowId ?? "",
    sessionId: sessionId ?? "",
  });

  function handleUpdateMessage(event: NewValueParams<any, string>) {
    const newValue = event.newValue;
    const field = event.column.getColId();
    const row = cloneDeep(event.data);
    const data = {
      ...row,
      [field]: newValue,
    };
    updateMessageMutation(data, {
      onSuccess: () => {
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
    });
  }

  const filteredMessages = useMemo(() => {
    let filteredMessages = sessionId
      ? messages.filter((message) => message.session_id === sessionId)
      : messages;
    filteredMessages = flowId
      ? filteredMessages.filter((message) => message.flow_id === flowId)
      : filteredMessages;
    return filteredMessages;
  }, [sessionId, flowId, messages]);

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
      alertTitle="No messages available"
      alertDescription="Try sending a message on the playground."
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
