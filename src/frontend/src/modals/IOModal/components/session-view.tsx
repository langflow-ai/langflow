import { useIsFetching } from "@tanstack/react-query";
import type { NewValueParams, SelectionChangedEvent } from "ag-grid-community";
import cloneDeep from "lodash/cloneDeep";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { removeMessages } from "@/components/core/playgroundComponent/chat-view/utils/message-utils";
import Loading from "@/components/ui/loading";
import {
  useDeleteMessages,
  useGetMessagesQuery,
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
  const { t } = useTranslation();
  const messages = useMessagesStore((state) => state.messages);
  const setMessages = useMessagesStore((state) => state.setMessages);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const updateMessage = useMessagesStore((state) => state.updateMessage);
  const deleteMessagesStore = useMessagesStore((state) => state.removeMessages);
  const playgroundPage = useFlowStore((state) => state.playgroundPage);
  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  // Fetch messages for the specific session
  const messageQueryParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (session) {
      params.session_id = session;
    }
    return {
      id: id,
      mode: "union" as const,
      params: params,
    };
  }, [session, id]);

  const { data: queryData, isFetching: isQueryFetching } = useGetMessagesQuery(
    messageQueryParams,
    {
      enabled: !playgroundPage, // Only fetch if not in playground page
    },
  );

  // Update messages store when data is fetched
  useEffect(() => {
    if (queryData && typeof queryData === "object" && "rows" in queryData) {
      const rowsData = queryData.rows as { data?: unknown[] } | undefined;
      if (rowsData && typeof rowsData === "object" && "data" in rowsData) {
        const fetchedMessages = rowsData.data || [];
        setMessages(fetchedMessages);
      }
    }
  }, [queryData, setMessages]);

  const columnHeaderMap: Record<string, string> = {
    timestamp: t("messages.column.timestamp"),
    text: t("messages.column.text"),
    sender: t("messages.column.sender"),
    sender_name: t("messages.column.senderName"),
    session_id: t("messages.column.sessionId"),
    files: t("messages.column.files"),
  };

  const columns = extractColumnsFromRows(messages, "intersection").map((col) =>
    col.field && columnHeaderMap[col.field]
      ? { ...col, headerName: columnHeaderMap[col.field] }
      : col,
  );
  const isFetchingCount = useIsFetching({
    queryKey: ["useGetMessagesQuery"],
    exact: false,
  });
  const isFetching = isFetchingCount > 0 || isQueryFetching;

  const { mutate: deleteMessages } = useDeleteMessages({
    onSuccess: () => {
      deleteMessagesStore(selectedRows);
      if (session && id) {
        removeMessages(selectedRows, session, id);
      }
      setSelectedRows([]);
      setSuccessData({
        title: t("success.messagesDeleted"),
      });
    },
    onError: () => {
      setErrorData({
        title: t("errors.deletingMessages"),
      });
    },
  });

  const { mutate: updateMessageMutation } = useUpdateMessage();

  function handleUpdateMessage(
    event: NewValueParams<Record<string, unknown>, string>,
  ) {
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
            title: t("success.messagesUpdated"),
          });
        },
        onError: () => {
          setErrorData({
            title: t("errors.updatingMessages"),
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

  return isFetching ? (
    <div className="flex h-full w-full items-center justify-center align-middle">
      <Loading></Loading>
    </div>
  ) : (
    <TableComponent
      key={"sessionView"}
      onDelete={playgroundPage ? undefined : handleRemoveMessages}
      readOnlyEdit
      editable={editable}
      overlayNoRowsTemplate={t("table.noRowsToShow")}
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
