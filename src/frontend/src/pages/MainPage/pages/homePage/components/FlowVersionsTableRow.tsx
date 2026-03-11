import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import type { FlowType } from "@/types/flow";
import type { FlowHistoryEntry } from "@/types/flow/history";
import { cn } from "@/utils/utils";
import { timeElapsed } from "../../../utils/time-elapse";

type FlowVersionsTableRowProps = {
  flow: FlowType;
  entries: FlowHistoryEntry[];
  hasLoadedHistory: boolean;
  versionCount: number | null;
  deployedEntryCount: number;
  deploymentCounts: Record<string, number>;
  isLoadingHistory: boolean;
  folderId?: string;
  tableGridCols: string;
  isExpanded: boolean;
  onToggleExpand: () => void;
};

export default function FlowVersionsTableRow({
  flow,
  entries,
  hasLoadedHistory,
  versionCount,
  deployedEntryCount,
  deploymentCounts,
  isLoadingHistory,
  folderId,
  tableGridCols,
  isExpanded,
  onToggleExpand,
}: FlowVersionsTableRowProps) {
  const navigate = useCustomNavigate();

  const flowStatus = deployedEntryCount > 0 ? "Deployed" : "Draft";
  const mockTimestamp = flow.updated_at ?? new Date().toISOString();
  const mockEntries: FlowHistoryEntry[] = [
    {
      id: `${flow.id}-mock-history-1`,
      flow_id: flow.id,
      user_id: flow.user_id ?? "",
      version_number: 1,
      created_at: mockTimestamp,
      description: "Mock version entry",
      version_tag: "v1",
    },
  ];
  const visibleEntries = entries.length > 0 ? entries : mockEntries;

  return (
    <div className="border-b border-border/60 last:border-b-0">
      <div
        className={cn(
          "grid w-full items-center px-4 py-5 text-left transition-colors hover:bg-muted/20",
          tableGridCols,
        )}
      >
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded pl-3 text-muted-foreground"
            onClick={(event) => {
              event.stopPropagation();
              onToggleExpand();
            }}
          >
            <ForwardedIconComponent
              name={isExpanded ? "ChevronDown" : "ChevronRight"}
              className="h-4 w-4 text-primary"
            />
          </button>
          <button
            type="button"
            className="truncate text-left text-sm font-medium"
            onClick={() => {
              navigate(
                `/flow/${flow.id}${folderId ? `/folder/${folderId}` : ""}`,
              );
            }}
          >
            {flow.name}
          </button>
        </div>
        <button
          type="button"
          className="text-left text-sm text-primary"
          onClick={() => {
            navigate(
              `/flow/${flow.id}${folderId ? `/folder/${folderId}` : ""}`,
            );
          }}
        >
          {hasLoadedHistory && versionCount !== null && versionCount > 0
            ? `${versionCount} versions`
            : "v1"}
        </button>
        <button
          type="button"
          className={cn(
            "inline-flex w-fit items-center gap-1 text-sm font-medium text-left text-primary",
          )}
          onClick={() => {
            navigate(
              `/flow/${flow.id}${folderId ? `/folder/${folderId}` : ""}`,
            );
          }}
        >
          <span
            className={cn(
              "h-2 w-2 rounded-full mr-1",
              flowStatus === "Deployed"
                ? "bg-emerald-500"
                : "bg-muted-foreground/60",
            )}
          />
          {flowStatus}
        </button>
        <button
          type="button"
          className="text-left text-sm text-primary"
          onClick={() => {
            navigate(
              `/flow/${flow.id}${folderId ? `/folder/${folderId}` : ""}`,
            );
          }}
        >
          {timeElapsed(flow.updated_at)} ago
        </button>
      </div>

      {isExpanded && !hasLoadedHistory && isLoadingHistory && (
        <div
          className={cn(
            "grid items-center border-t border-border/50 px-4 py-5 text-sm text-muted-foreground",
            tableGridCols,
          )}
        >
          <span className="pl-11">Loading versions...</span>
          <span>-</span>
          <span>-</span>
          <span>-</span>
        </div>
      )}
      {isExpanded &&
        !isLoadingHistory &&
        visibleEntries.map((entry) => {
          const isDeployed = (deploymentCounts[entry.id] ?? 0) > 0;
          return (
            <div
              key={entry.id}
              className={cn(
                "grid items-center border-t border-border/50 px-4 py-5 text-sm transition-colors bg-muted/20",
                tableGridCols,
              )}
            >
              <button
                type="button"
                className="col-span-4 grid grid-cols-[2.4fr_1fr_1fr_1.2fr] items-center text-left text-muted-foreground"
                onClick={() => {
                  const targetPath = `/flow/${flow.id}${folderId ? `/folder/${folderId}` : ""}`;
                  navigate(
                    `${targetPath}?historyId=${encodeURIComponent(entry.id)}`,
                  );
                }}
              >
                <div className="flex items-center gap-2 pl-[36px] text-muted-foreground">
                  <span className="truncate">
                    {entry.description?.trim() ? entry.description : flow.name}
                  </span>
                </div>
                <span>{entry.version_tag}</span>
                <span
                  className={cn(
                    "inline-flex w-fit items-center gap-1 text-sm font-medium",
                    isDeployed ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full mr-1",
                      isDeployed ? "bg-emerald-500" : "bg-muted-foreground/60",
                    )}
                  />
                  {isDeployed ? "Deployed" : "Draft"}
                </span>
                <span className="text-muted-foreground">
                  {timeElapsed(entry.created_at)} ago
                </span>
              </button>
            </div>
          );
        })}
    </div>
  );
}
