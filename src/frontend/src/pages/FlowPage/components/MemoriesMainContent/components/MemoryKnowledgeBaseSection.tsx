import type { UIEvent } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import Loading from "@/components/ui/loading";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils/utils";
import { formatTimestamp } from "../helpers";
import { MemoryKnowledgeBaseSectionProps } from "../types";

export function MemoryKnowledgeBaseSection({
  docsData,
  docsLoading,
  fetchNextMessagesPage,
  hasNextMessagesPage,
  isFetchingNextMessagesPage,
  setSelectedSession,
  groupedBySession,
  handleOpenDocumentPanel,
}: MemoryKnowledgeBaseSectionProps) {
  const handleScroll = (e: UIEvent<HTMLDivElement>) => {
    if (!hasNextMessagesPage || isFetchingNextMessagesPage) return;
    const el = e.currentTarget;
    const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (remaining < 240) {
      fetchNextMessagesPage();
    }
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold">Memory Base</h3>
          <span className="text-xs text-muted-foreground">
            {docsData?.total ?? 0} chunks
          </span>
        </div>
        <div className="flex items-center gap-2" />
      </div>

      <div className="flex-1 overflow-auto" onScroll={handleScroll}>
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
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-32 text-xs">Session</TableHead>
                <TableHead className="w-24 text-xs">Sender</TableHead>
                <TableHead className="w-40 text-xs">Ingestion Job</TableHead>
                <TableHead className="text-xs">Content</TableHead>
                <TableHead className="w-44 text-xs">
                  Ingestion Timestamp
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from(groupedBySession.entries()).map(([sessionId, docs]) =>
                docs.map((doc, index) => (
                  <TableRow
                    key={`${sessionId}-${doc.message_id}-${index}`}
                    className={cn(
                      "cursor-pointer",
                      index === 0 && sessionId !== "(no session)"
                        ? "border-t-2 border-t-border"
                        : "",
                    )}
                    onClick={() => handleOpenDocumentPanel(doc)}
                  >
                    <TableCell className="text-xs text-muted-foreground">
                      {index === 0 ? (
                        <span
                          className="cursor-pointer truncate font-medium text-foreground hover:underline"
                          title={sessionId}
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setSelectedSession(sessionId);
                          }}
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
                    <TableCell className="max-w-40 truncate text-xs text-muted-foreground">
                      {doc.ingestion_job_id || "-"}
                    </TableCell>
                    <TableCell className="max-w-md text-xs">
                      <div className="line-clamp-2" title={doc.content}>
                        {doc.content}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatTimestamp(
                        doc.ingestion_timestamp || doc.timestamp,
                      )}
                    </TableCell>
                  </TableRow>
                )),
              )}

              {isFetchingNextMessagesPage && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={5} className="py-4">
                    <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
                      <Loading size={16} className="text-muted-foreground" />
                      Loading more...
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
