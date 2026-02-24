import { useIsFetching } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import Loading from "@/components/ui/loading";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useDeleteMessages,
  useGetMessagesQuery,
} from "@/controllers/API/queries/messages";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useMessagesStore } from "@/stores/messagesStore";
import CreateDatasetFromMessagesModal from "@/modals/createDatasetFromMessagesModal";

interface MessagesMainContentProps {
  selectedSessionId?: string | null;
}

const ExpandableCell = ({ text }: { text?: string | null }) => {
  const [expanded, setExpanded] = useState(false);

  if (!text) {
    return <span className="text-muted-foreground">-</span>;
  }

  return (
    <div
      className={
        expanded
          ? "max-w-96 cursor-pointer whitespace-pre-wrap break-words py-1"
          : "max-w-48 cursor-pointer truncate"
      }
      onClick={() => setExpanded(!expanded)}
      title={expanded ? "Click to collapse" : "Click to expand"}
    >
      {text}
    </div>
  );
};

const formatTimestamp = (ts?: string) => {
  if (!ts) return "-";
  try {
    // Handle "YYYY-MM-DD HH:MM:SS" format by replacing space with T
    const normalized = ts.includes("T") ? ts : ts.replace(" ", "T");
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return ts;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
};

export default function MessagesMainContent({
  selectedSessionId,
}: MessagesMainContentProps) {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const messages = useMessagesStore((state) => state.messages);
  const deleteMessagesStore = useMessagesStore((state) => state.removeMessages);
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
  const [createDatasetModalOpen, setCreateDatasetModalOpen] = useState(false);
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
      deleteMessagesStore(Array.from(selectedRows));
      setSelectedRows(new Set());
      setSuccessData({ title: "Messages deleted successfully." });
    },
    onError: () => {
      setErrorData({ title: "Error deleting messages." });
    },
  });

  const filteredMessages = useMemo(() => {
    let filtered = messages;
    if (currentFlowId) {
      filtered = filtered.filter((m) => m.flow_id === currentFlowId);
    }
    if (selectedSessionId !== null && selectedSessionId !== undefined) {
      filtered = filtered.filter(
        (m) => (m.session_id || "") === selectedSessionId,
      );
    }
    return filtered;
  }, [messages, currentFlowId, selectedSessionId]);

  const sessionsForModal = useMemo(() => {
    const allFlowMessages = currentFlowId
      ? messages.filter((m) => m.flow_id === currentFlowId)
      : messages;
    const sessionMap = new Map<
      string,
      { count: number; lastTimestamp: string }
    >();
    for (const msg of allFlowMessages) {
      const sid = msg.session_id || "";
      const existing = sessionMap.get(sid);
      if (!existing) {
        sessionMap.set(sid, { count: 1, lastTimestamp: msg.timestamp || "" });
      } else {
        existing.count += 1;
        if (msg.timestamp > existing.lastTimestamp) {
          existing.lastTimestamp = msg.timestamp;
        }
      }
    }
    return Array.from(sessionMap.entries()).map(([id, data]) => ({
      id,
      messageCount: data.count,
      lastTimestamp: data.lastTimestamp,
    }));
  }, [messages, currentFlowId]);

  const allSelected =
    filteredMessages.length > 0 &&
    filteredMessages.every((m) => selectedRows.has(m.id));

  const toggleAll = () => {
    if (allSelected) {
      setSelectedRows(new Set());
    } else {
      setSelectedRows(new Set(filteredMessages.map((m) => m.id)));
    }
  };

  const toggleRow = (id: string) => {
    setSelectedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleDelete = () => {
    if (selectedRows.size > 0) {
      deleteMessages({ ids: Array.from(selectedRows) });
    }
  };

  const sessionLabel = selectedSessionId
    ? selectedSessionId.length > 30
      ? `${selectedSessionId.slice(0, 30)}...`
      : selectedSessionId
    : "All Sessions";

  return (
    <div className="flex h-full w-full flex-col bg-muted/30">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-background px-6 py-3">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold">Messages</h2>
          <span className="text-xs text-muted-foreground">&middot;</span>
          <span className="text-xs text-muted-foreground">{sessionLabel}</span>
          <span className="text-xs text-muted-foreground">&middot;</span>
          <span className="text-xs text-muted-foreground">
            {filteredMessages.length} message
            {filteredMessages.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {selectedRows.size > 0 && (
            <Button variant="outline" size="sm" onClick={handleDelete}>
              <IconComponent name="Trash2" className="mr-1.5 h-3.5 w-3.5" />
              Delete ({selectedRows.size})
            </Button>
          )}
          {sessionsForModal.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCreateDatasetModalOpen(true)}
            >
              <IconComponent
                name="TableProperties"
                className="mr-1.5 h-3.5 w-3.5"
              />
              Create Dataset
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col overflow-hidden p-4">
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
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
            <div className="flex-1 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-10">
                      <Checkbox
                        checked={allSelected}
                        onCheckedChange={toggleAll}
                      />
                    </TableHead>
                    <TableHead className="w-40 text-xs">Timestamp</TableHead>
                    <TableHead className="text-xs">Text</TableHead>
                    <TableHead className="w-24 text-xs">Sender</TableHead>
                    <TableHead className="w-24 text-xs">Name</TableHead>
                    <TableHead className="w-16 text-xs">Files</TableHead>
                    <TableHead className="w-16 text-xs">Error</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredMessages.map((msg: any) => (
                    <TableRow key={msg.id}>
                      <TableCell>
                        <Checkbox
                          checked={selectedRows.has(msg.id)}
                          onCheckedChange={() => toggleRow(msg.id)}
                        />
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatTimestamp(msg.timestamp)}
                      </TableCell>
                      <TableCell className="text-xs">
                        <ExpandableCell text={msg.text} />
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {msg.sender || "-"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {msg.sender_name || "-"}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {Array.isArray(msg.files) && msg.files.length > 0 ? (
                          <ExpandableCell text={msg.files.join(", ")} />
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell className="text-xs">
                        {msg.error ? (
                          <span className="text-destructive">Yes</span>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </div>

      <CreateDatasetFromMessagesModal
        open={createDatasetModalOpen}
        setOpen={setCreateDatasetModalOpen}
        flowId={currentFlowId || ""}
        sessions={sessionsForModal}
        selectedSessionId={selectedSessionId}
      />
    </div>
  );
}
