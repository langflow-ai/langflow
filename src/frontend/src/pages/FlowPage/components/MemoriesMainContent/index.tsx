import { useEffect, useMemo, useRef, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import Loading from "@/components/ui/loading";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useGetMemory } from "@/controllers/API/queries/memories/use-get-memory";
import { useUpdateMemoryKB } from "@/controllers/API/queries/memories/use-update-memory-kb";
import { useDeleteMemory } from "@/controllers/API/queries/memories/use-delete-memory";
import { useUpdateMemory } from "@/controllers/API/queries/memories/use-update-memory";
import {
  useGetMemoryDocuments,
  type MemoryDocumentItem,
} from "@/controllers/API/queries/memories/use-get-memory-documents";
import type { MemoryInfo } from "@/controllers/API/queries/memories/use-get-memories";
import useAlertStore from "@/stores/alertStore";
import { cn } from "@/utils/utils";

interface MemoriesMainContentProps {
  selectedMemoryId?: string | null;
  onSelectMemory?: (id: string | null) => void;
}

const statusColors: Record<string, string> = {
  idle: "text-muted-foreground",
  generating: "text-primary",
  updating: "text-primary",
  failed: "text-destructive",
};

const statusBgColors: Record<string, string> = {
  idle: "bg-muted",
  generating: "bg-primary/10",
  updating: "bg-primary/10",
  failed: "bg-destructive/10",
};

const formatDate = (dateStr?: string) => {
  if (!dateStr) return "Never";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
};

const formatTimestamp = (ts?: string) => {
  if (!ts) return "-";
  try {
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

const NoMemorySelected = () => (
  <div className="flex h-full w-full flex-col items-center justify-center text-center">
    <IconComponent
      name="Brain"
      className="mb-3 h-12 w-12 text-muted-foreground opacity-50"
    />
    <p className="text-sm text-muted-foreground">No memory selected</p>
    <p className="mt-1 text-xs text-muted-foreground">
      Select a memory from the sidebar to view details
    </p>
  </div>
);

const SummaryCard = ({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon: string;
}) => (
  <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-3">
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted">
      <IconComponent name={icon} className="h-4 w-4 text-muted-foreground" />
    </div>
    <div className="flex flex-col">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  </div>
);

export default function MemoriesMainContent({
  selectedMemoryId,
  onSelectMemory,
}: MemoriesMainContentProps) {
  const { setErrorData, setSuccessData } = useAlertStore();
  const [searchQuery, setSearchQuery] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  // Reset search/filter state when switching memories
  const prevMemoryIdRef = useRef(selectedMemoryId);
  useEffect(() => {
    if (prevMemoryIdRef.current !== selectedMemoryId) {
      prevMemoryIdRef.current = selectedMemoryId;
      setSearchQuery("");
      setActiveSearch("");
      setSelectedSession(null);
    }
  }, [selectedMemoryId]);

  const {
    data: memory,
    isLoading,
    isError,
  } = useGetMemory(
    { memoryId: selectedMemoryId ?? "" },
    {
      enabled: !!selectedMemoryId,
      refetchInterval: (query) => {
        const data = query.state.data as MemoryInfo | undefined;
        return data?.status === "generating" || data?.status === "updating"
          ? 2000
          : false;
      },
      retry: false,
    },
  );

  // If the memory was deleted externally (404), clear selection
  useEffect(() => {
    if (isError && selectedMemoryId) {
      onSelectMemory?.(null);
    }
  }, [isError, selectedMemoryId, onSelectMemory]);

  const {
    data: docsData,
    isLoading: docsLoading,
    refetch: refetchDocs,
  } = useGetMemoryDocuments(
    {
      memoryId: selectedMemoryId ?? "",
      search: activeSearch || undefined,
      limit: 500,
    },
    { enabled: !!selectedMemoryId },
  );

  // Refetch documents when memory finishes processing (status transitions to idle)
  const prevStatusRef = useRef(memory?.status);
  useEffect(() => {
    const prev = prevStatusRef.current;
    const curr = memory?.status;
    prevStatusRef.current = curr;
    if (
      (prev === "generating" || prev === "updating") &&
      curr === "idle"
    ) {
      refetchDocs();
    }
  }, [memory?.status, refetchDocs]);

  const updateKBMutation = useUpdateMemoryKB({
    onSuccess: () => {
      setSuccessData({ title: "Memory update started" });
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to update memory",
        list: [error?.response?.data?.detail || error?.message],
      });
    },
  });

  const deleteMutation = useDeleteMemory({
    onSuccess: () => {
      setSuccessData({ title: "Memory deleted" });
      onSelectMemory?.(null);
    },
    onError: (error: any) => {
      setErrorData({
        title: "Failed to delete memory",
        list: [error?.response?.data?.detail || error?.message],
      });
    },
  });

  const updateMemoryMutation = useUpdateMemory({
    onError: (error: any) => {
      setErrorData({
        title: "Failed to update memory",
        list: [error?.response?.data?.detail || error?.message],
      });
    },
  });

  const handleToggleActive = () => {
    if (!memory) return;
    updateMemoryMutation.mutate({
      memoryId: memory.id,
      is_active: !memory.is_active,
    });
  };

  // Group documents by session
  const groupedBySession = useMemo(() => {
    if (!docsData?.documents) return new Map<string, MemoryDocumentItem[]>();
    const map = new Map<string, MemoryDocumentItem[]>();
    for (const doc of docsData.documents) {
      const sid = doc.session_id || "(no session)";
      if (selectedSession && sid !== selectedSession) continue;
      const list = map.get(sid) || [];
      list.push(doc);
      map.set(sid, list);
    }
    return map;
  }, [docsData, selectedSession]);

  const handleSearch = () => {
    setActiveSearch(searchQuery);
    setSelectedSession(null);
  };

  if (!selectedMemoryId) {
    return <NoMemorySelected />;
  }

  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loading size={64} className="text-primary" />
      </div>
    );
  }

  if (!memory) {
    return <NoMemorySelected />;
  }

  const isProcessing =
    memory.status === "generating" || memory.status === "updating";

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-muted/30">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-background px-6 py-3">
        <div className="flex items-center gap-3">
          <IconComponent
            name="Brain"
            className="h-5 w-5 text-muted-foreground"
          />
          <div>
            <h2 className="text-sm font-semibold">{memory.name}</h2>
            {memory.description && (
              <p className="text-xs text-muted-foreground">
                {memory.description}
              </p>
            )}
          </div>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-medium",
              statusBgColors[memory.status] || "bg-muted",
              statusColors[memory.status] || "text-muted-foreground",
            )}
          >
            {memory.status}
          </span>
          {/* Auto-capture toggle */}
          <div className="ml-2 flex items-center gap-2">
            <Switch
              checked={memory.is_active}
              onCheckedChange={handleToggleActive}
              disabled={updateMemoryMutation.isPending}
            />
            <span
              className={cn(
                "text-xs font-medium",
                memory.is_active ? "text-success" : "text-muted-foreground",
              )}
            >
              {memory.is_active ? "Auto-capture on" : "Auto-capture off"}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              updateKBMutation.mutate({ memoryId: memory.id })
            }
            disabled={isProcessing}
          >
            <IconComponent
              name="RefreshCw"
              className="mr-1.5 h-3.5 w-3.5"
            />
            Manual Update
          </Button>
          <DeleteConfirmationModal
            description={`memory "${memory.name}"`}
            onConfirm={() =>
              deleteMutation.mutate({ memoryId: memory.id })
            }
            asChild
          >
            <Button variant="outline" size="sm">
              <IconComponent
                name="Trash2"
                className="mr-1.5 h-3.5 w-3.5"
              />
              Delete
            </Button>
          </DeleteConfirmationModal>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col overflow-auto p-4">
        {/* Progress indicator */}
        {isProcessing && (
          <div className="mb-4 rounded-lg border border-primary/20 bg-primary/5 p-4">
            <div className="flex items-center gap-3">
              <IconComponent name="Loader2" className="h-5 w-5 animate-spin text-primary" />
              <div>
                <p className="text-sm font-medium">
                  {memory.status === "generating"
                    ? "Generating memory..."
                    : "Updating memory..."}
                </p>
                <p className="text-xs text-muted-foreground">
                  Vectorizing messages into the knowledge base.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error display */}
        {memory.status === "failed" && memory.error_message && (
          <div className="mb-4 rounded-lg border border-destructive/20 bg-destructive/5 p-4">
            <div className="flex items-start gap-3">
              <IconComponent
                name="AlertTriangle"
                className="mt-0.5 h-5 w-5 text-destructive"
              />
              <div>
                <p className="text-sm font-medium text-destructive">
                  Generation Failed
                </p>
                <p className="mt-1 text-xs text-destructive/80">
                  {memory.error_message}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Summary cards */}
        <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <SummaryCard
            label="Messages Processed"
            value={memory.total_messages_processed}
            icon="MessageSquare"
          />
          <SummaryCard
            label="Total Chunks"
            value={memory.total_chunks}
            icon="Layers"
          />
          <SummaryCard
            label="Sessions Captured"
            value={memory.sessions_count}
            icon="Users"
          />
          <SummaryCard
            label="Last Generated"
            value={formatDate(memory.last_generated_at)}
            icon="Clock"
          />
        </div>

        {/* Model info row */}
        <div className="mb-4 flex items-center gap-4 text-xs text-muted-foreground">
          <span>
            <span className="font-medium text-foreground">KB:</span>{" "}
            <a
              href={`/assets/knowledge-bases?kb=${encodeURIComponent(memory.kb_name.replace(/[_-]/g, " "))}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-muted-foreground/50 underline-offset-2 hover:text-foreground"
            >
              {memory.kb_name}
            </a>
          </span>
          <span>&middot;</span>
          <span>
            <span className="font-medium text-foreground">Model:</span>{" "}
            {memory.embedding_model}
          </span>
          <span>&middot;</span>
          <span>
            <span className="font-medium text-foreground">Provider:</span>{" "}
            {memory.embedding_provider}
          </span>
        </div>

        {/* Documents section */}
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
          {/* Documents header */}
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-semibold">Knowledge Base</h3>
              <span className="text-xs text-muted-foreground">
                {docsData?.total ?? 0} chunks
              </span>
            </div>
            <div className="flex items-center gap-2">
              {/* Session filter */}
              {docsData?.sessions && docsData.sessions.length > 1 && (
                <select
                  className="h-7 rounded border border-border bg-background px-2 text-xs"
                  value={selectedSession ?? ""}
                  onChange={(e) =>
                    setSelectedSession(e.target.value || null)
                  }
                >
                  <option value="">All sessions</option>
                  {docsData.sessions.map((sid) => (
                    <option key={sid} value={sid}>
                      {sid.length > 20 ? `${sid.slice(0, 20)}...` : sid}
                    </option>
                  ))}
                </select>
              )}
              {/* Search */}
              <div className="flex items-center gap-1">
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  placeholder="Search chunks..."
                  className="h-7 w-40 text-xs"
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={handleSearch}
                >
                  <IconComponent name="Search" className="h-3.5 w-3.5" />
                </Button>
                {activeSearch && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => {
                      setSearchQuery("");
                      setActiveSearch("");
                    }}
                  >
                    <IconComponent name="X" className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            </div>
          </div>

          {/* Documents table */}
          <div className="flex-1 overflow-auto">
            {docsLoading ? (
              <div className="flex h-32 items-center justify-center">
                <Loading size={32} className="text-primary" />
              </div>
            ) : !docsData?.documents?.length ? (
              <div className="flex h-32 flex-col items-center justify-center text-center">
                <IconComponent
                  name="Database"
                  className="mb-2 h-8 w-8 text-muted-foreground opacity-50"
                />
                <p className="text-xs text-muted-foreground">
                  {activeSearch
                    ? "No matching documents found"
                    : memory.total_chunks > 0
                      ? "Knowledge base may have been deleted externally. Try regenerating."
                      : "No documents yet. Generate to vectorize messages."}
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-32 text-xs">Session</TableHead>
                    <TableHead className="w-24 text-xs">Sender</TableHead>
                    <TableHead className="text-xs">Content</TableHead>
                    <TableHead className="w-36 text-xs">Timestamp</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Array.from(groupedBySession.entries()).map(
                    ([sessionId, docs]) =>
                      docs.map((doc, i) => (
                        <TableRow
                          key={`${doc.message_id}-${i}`}
                          className={cn(
                            i === 0 && sessionId !== "(no session)"
                              ? "border-t-2 border-t-border"
                              : "",
                          )}
                        >
                          <TableCell className="text-xs text-muted-foreground">
                            {i === 0 ? (
                              <span
                                className="cursor-pointer truncate font-medium text-foreground hover:underline"
                                title={sessionId}
                                onClick={() =>
                                  setSelectedSession(
                                    selectedSession === sessionId
                                      ? null
                                      : sessionId,
                                  )
                                }
                              >
                                {sessionId === "(no session)"
                                  ? sessionId
                                  : sessionId.length > 12
                                    ? `${sessionId.slice(0, 12)}...`
                                    : sessionId}
                              </span>
                            ) : (
                              ""
                            )}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {doc.sender || "-"}
                          </TableCell>
                          <TableCell className="max-w-md text-xs">
                            <div
                              className="line-clamp-2 cursor-pointer"
                              title={doc.content}
                            >
                              {doc.content}
                            </div>
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {formatTimestamp(doc.timestamp)}
                          </TableCell>
                        </TableRow>
                      )),
                  )}
                </TableBody>
              </Table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
