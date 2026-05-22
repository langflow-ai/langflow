import type { UIEvent } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import StringReader from "@/components/common/stringReaderComponent";
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
import { KNOWLEDGE_BASE_SCROLL_THRESHOLD_PX } from "../MemoriesMainContent.constants";
import { MemoryKnowledgeBaseSectionProps } from "../types";

const noop = () => {};

export function MemoryKnowledgeBaseSection({
  docsData,
  docsLoading,
  fetchNextMessagesPage,
  hasNextMessagesPage,
  isFetchingNextMessagesPage,
  groupedBySession,
  handleOpenDocumentPanel,
}: MemoryKnowledgeBaseSectionProps) {
  const { t } = useTranslation();
  const handleScroll = (e: UIEvent<HTMLDivElement>) => {
    if (!hasNextMessagesPage || isFetchingNextMessagesPage) return;
    const el = e.currentTarget;
    const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (remaining < KNOWLEDGE_BASE_SCROLL_THRESHOLD_PX) {
      fetchNextMessagesPage();
    }
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold">{t("memory.memoryBase")}</h3>
          <span className="text-xs text-muted-foreground">
            {docsData?.total ?? 0} chunks
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-auto" onScroll={handleScroll}>
        {docsLoading ? (
          <div className="flex h-32 items-center justify-center">
            <Loading size={32} className="text-primary" />
          </div>
        ) : !docsData?.documents?.length ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <IconComponent
              name="Database"
              className="h-8 w-8 text-muted-foreground opacity-50"
            />
            <p className="text-sm font-medium text-foreground">
              {t("memory.noChunksYet")}
            </p>
            <p className="max-w-xs text-xs text-muted-foreground">
              {t("memory.noChunksRunFlow")}
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-24 text-xs">Sender</TableHead>
                <TableHead className="w-40 text-xs">Job ID</TableHead>
                <TableHead className="text-xs">Content</TableHead>
                <TableHead className="w-44 text-xs">
                  Ingestion Timestamp
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Array.from(groupedBySession.entries()).map(([sessionId, docs]) =>
                docs.map((doc, idx) => (
                  <TableRow
                    key={`${sessionId}-${doc.message_id}`}
                    className={cn(
                      "cursor-pointer",
                      idx === 0 && sessionId !== "(no session)"
                        ? "border-t-2 border-t-border"
                        : "",
                    )}
                    onClick={() => handleOpenDocumentPanel(doc)}
                  >
                    <TableCell
                      className="text-xs text-muted-foreground [&>button]:text-left"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <StringReader
                        editable={false}
                        setValue={noop}
                        string={doc.sender || "-"}
                      />
                    </TableCell>
                    <TableCell
                      className="max-w-40 overflow-hidden text-xs text-muted-foreground [&>button]:text-left"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <StringReader
                        editable={false}
                        setValue={noop}
                        string={doc.job_id || "-"}
                      />
                    </TableCell>
                    <TableCell
                      className="max-w-md overflow-hidden text-xs [&>button]:text-left"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <StringReader
                        editable={false}
                        setValue={noop}
                        string={doc.content}
                      />
                    </TableCell>
                    <TableCell
                      className="text-xs text-muted-foreground [&>button]:text-left"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <StringReader
                        editable={false}
                        setValue={noop}
                        string={formatTimestamp(
                          doc.ingestion_timestamp || doc.timestamp,
                        )}
                      />
                    </TableCell>
                  </TableRow>
                )),
              )}

              {isFetchingNextMessagesPage && (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={4} className="py-4">
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
