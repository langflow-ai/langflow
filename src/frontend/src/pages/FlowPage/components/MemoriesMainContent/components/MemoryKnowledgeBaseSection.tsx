import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  searchQuery,
  setSearchQuery,
  activeSearch,
  setActiveSearch,
  selectedSession,
  setSelectedSession,
  handleSearch,
  groupedBySession,
  handleOpenDocumentPanel,
  totalChunks,
}: MemoryKnowledgeBaseSectionProps) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold">Knowledge Base</h3>
          <span className="text-xs text-muted-foreground">
            {docsData?.total ?? 0} chunks
          </span>
        </div>
        <div className="flex items-center gap-2">
          {docsData?.sessions && docsData.sessions.length > 1 && (
            <select
              aria-label="Session filter"
              className="h-7 rounded border border-border bg-background px-2 text-xs"
              value={selectedSession ?? ""}
              onChange={(e) => setSelectedSession(e.target.value || null)}
            >
              <option value="">All sessions</option>
              {docsData.sessions.map((sid) => (
                <option key={sid} value={sid}>
                  {sid.length > 20 ? `${sid.slice(0, 20)}...` : sid}
                </option>
              ))}
            </select>
          )}

          <div className="flex items-center gap-1">
            <Input
              aria-label="Search chunks"
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
              aria-label="Search"
              onClick={handleSearch}
            >
              <IconComponent name="Search" className="h-3.5 w-3.5" />
            </Button>
            {activeSearch && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label="Clear search"
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
                : totalChunks > 0
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
              {Array.from(groupedBySession.entries()).map(([sessionId, docs]) =>
                docs.map((doc, index) => (
                  <TableRow
                    key={`${doc.message_id}-${index}`}
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
                            setSelectedSession(
                              selectedSession === sessionId ? null : sessionId,
                            );
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
                    <TableCell className="max-w-md text-xs">
                      <div className="line-clamp-2" title={doc.content}>
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
  );
}
