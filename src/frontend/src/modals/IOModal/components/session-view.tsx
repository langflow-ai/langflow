import type {
  CellKeyDownEvent,
  NewValueParams,
  SelectionChangedEvent,
  SuppressKeyboardEventParams,
} from "ag-grid-community";
import cloneDeep from "lodash/cloneDeep";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { removeMessages } from "@/components/core/playgroundComponent/chat-view/utils/message-utils";
import Loading from "@/components/ui/loading";
import {
  useDeleteMessages,
  useUpdateMessage,
} from "@/controllers/API/queries/messages";
import { useGetMessageHistory } from "@/controllers/API/queries/messages/use-get-message-history";
import useFlowStore from "@/stores/flowStore";
import TableComponent from "../../../components/core/parameterRenderComponent/components/tableComponent";
import useAlertStore from "../../../stores/alertStore";
import { useMessagesStore } from "../../../stores/messagesStore";
import { extractColumnsFromRows, messagesSorter } from "../../../utils/utils";
import { MessageHistoryLoader } from "./message-history-loader";

function suppressMessageRowActionKeys(params: SuppressKeyboardEventParams) {
  return (
    params.event.key === "Enter" ||
    params.event.key === " " ||
    params.event.key === "Spacebar"
  );
}

export default function SessionView({
  session,
  id,
}: {
  session?: string;
  id?: string;
}) {
  const { t } = useTranslation();
  const messages = useMessagesStore((state) => state.messages);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const updateMessage = useMessagesStore((state) => state.updateMessage);
  const deleteMessagesStore = useMessagesStore((state) => state.removeMessages);
  const playgroundPage = useFlowStore((state) => state.playgroundPage);
  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  const history = useGetMessageHistory({
    id,
    sessionId: session,
    enabled: !playgroundPage,
  });

  const columnHeaderMap: Record<string, string> = {
    timestamp: t("messages.column.timestamp"),
    text: t("messages.column.text"),
    sender: t("messages.column.sender"),
    sender_name: t("messages.column.senderName"),
    session_id: t("messages.column.sessionId"),
    files: t("messages.column.files"),
  };

  const columns = extractColumnsFromRows(messages, "intersection").map(
    (col) => ({
      ...col,
      ...(col.field && columnHeaderMap[col.field]
        ? { headerName: columnHeaderMap[col.field] }
        : {}),
      ...(col.field === "text"
        ? { flex: 3, minWidth: 320, tooltipField: "text" }
        : {}),
      suppressKeyboardEvent: suppressMessageRowActionKeys,
    }),
  );
  const isFetching = !playgroundPage && history.isLoading;

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

  function handleCellKeyDown(event: CellKeyDownEvent) {
    const keyboardEvent = event.event as KeyboardEvent | undefined;
    if (keyboardEvent?.key !== " " && keyboardEvent?.key !== "Spacebar") {
      return;
    }

    keyboardEvent.preventDefault();
    keyboardEvent.stopPropagation();
    event.node.setSelected(!event.node.isSelected(), false);
    setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
  }

  const editable = useMemo(() => {
    return playgroundPage
      ? false
      : [{ field: "text", onUpdate: handleUpdateMessage, editableCell: false }];
  }, [handleUpdateMessage]);

  return isFetching ? (
    <div
      aria-label={t("common.loading")}
      className="flex h-full w-full items-center justify-center align-middle"
      role="status"
    >
      <Loading></Loading>
    </div>
  ) : (
    <div className="flex h-full min-h-0 flex-col">
      {!playgroundPage && <MessageHistoryLoader history={history} />}
      <TableComponent
        key={"sessionView"}
        tableLabel={t("messages.title")}
        onDelete={playgroundPage ? undefined : handleRemoveMessages}
        readOnlyEdit
        editable={editable}
        overlayNoRowsTemplate={t("table.noRowsToShow")}
        onSelectionChanged={(event: SelectionChangedEvent) => {
          setSelectedRows(event.api.getSelectedRows().map((row) => row.id));
        }}
        onCellKeyDown={handleCellKeyDown}
        rowSelection={playgroundPage ? undefined : "multiple"}
        suppressRowClickSelection={true}
        pagination={true}
        columnDefs={columns.sort(messagesSorter)}
        rowData={filteredMessages}
      />
    </div>
  );
}
