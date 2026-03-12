import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import type { FlowType } from "@/types/flow";
import type { FlowHistoryEntry } from "@/types/flow/history";
import { cn } from "@/utils/utils";
import DropdownComponent from "../../../components/dropdown";
import { timeElapsed } from "../../../utils/time-elapse";

type FlowVersionsTableRowProps = {
  flow: FlowType;
  entries: FlowHistoryEntry[];
  hasLoadedHistory: boolean;
  versionCount: number | null;
  deployedEntryCount: number;
  deploymentCounts: Record<string, number>;
  deploymentMatchesByHistoryId: Record<
    string,
    Array<{
      id: string;
      name: string;
      type: string;
      mode?: string;
    }>
  >;
  isLoadingHistory: boolean;
  canExpand: boolean;
  folderId?: string;
  tableGridCols: string;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onSetActionFlow: (
    flow: FlowType,
    action: "delete" | "export" | "settings",
  ) => void;
};

export default function FlowVersionsTableRow({
  flow,
  entries,
  hasLoadedHistory,
  versionCount,
  deployedEntryCount,
  deploymentCounts,
  deploymentMatchesByHistoryId,
  isLoadingHistory,
  canExpand,
  folderId,
  tableGridCols,
  isExpanded,
  onToggleExpand,
  onSetActionFlow,
}: FlowVersionsTableRowProps) {
  const navigate = useCustomNavigate();

  const flowStatus = deployedEntryCount > 0 ? "Deployed" : "Draft";
  return (
    <div className="border-b border-border/60 last:border-b-0">
      <div
        className={cn(
          "grid w-full items-center px-4 py-5 text-left transition-colors hover:bg-muted/20",
          tableGridCols,
        )}
      >
        <div className="flex items-center gap-2">
          {canExpand ? (
            <button
              type="button"
              className="rounded pl-3 text-muted-foreground"
              onClick={(event) => {
                event.stopPropagation();
                onToggleExpand();
              }}
            >
              <ForwardedIconComponent
                name="ChevronRight"
                className={cn(
                  "h-4 w-4 text-primary transition-transform duration-200 ease-in-out",
                  isExpanded && "rotate-90",
                )}
              />
            </button>
          ) : (
            <span className="h-4 w-4 pl-3" />
          )}
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
        <span className="flex justify-center">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="iconSm"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                onClick={(event) => {
                  event.stopPropagation();
                }}
              >
                <ForwardedIconComponent
                  name="EllipsisVertical"
                  className="h-4 w-4"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className="w-[185px]"
              sideOffset={5}
              side="bottom"
              align="end"
              onClick={(event) => {
                event.stopPropagation();
              }}
            >
              <DropdownComponent
                flowData={flow}
                setOpenDelete={(open) => {
                  if (open) onSetActionFlow(flow, "delete");
                }}
                handleExport={() => {
                  onSetActionFlow(flow, "export");
                }}
                handleEdit={() => {
                  onSetActionFlow(flow, "settings");
                }}
              />
            </DropdownMenuContent>
          </DropdownMenu>
        </span>
      </div>

      {canExpand && (
        <div
          className={cn(
            "grid transition-all duration-300 ease-in-out",
            isExpanded
              ? "grid-rows-[1fr] opacity-100"
              : "grid-rows-[0fr] opacity-0",
          )}
        >
          <div className="overflow-hidden">
            {!hasLoadedHistory && isLoadingHistory && (
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
                <span />
              </div>
            )}
            {!isLoadingHistory &&
              entries.map((entry) => {
                const matchedDeployments =
                  deploymentMatchesByHistoryId[entry.id] ?? [];
                const isDeployed =
                  matchedDeployments.length > 0 ||
                  (deploymentCounts[entry.id] ?? 0) > 0;

                const deploymentNames = matchedDeployments
                  .map((deployment) => deployment.name.trim())
                  .filter(Boolean)
                  .join(", ");

                return (
                  <div
                    key={entry.id}
                    className={cn(
                      "grid items-center border-t border-border/50 px-4 py-5 text-sm transition-colors hover:bg-muted/20",
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
                        <div className="min-w-0">
                          <span className="block truncate">
                            {entry.description?.trim()
                              ? entry.description
                              : flow.name}
                          </span>
                          {deploymentNames && (
                            <span className="mt-0.5 block truncate text-xs">
                              Deployments: {deploymentNames}
                            </span>
                          )}
                        </div>
                      </div>
                      <span>{entry.version_tag}</span>
                      <span
                        className={cn(
                          "inline-flex w-fit items-center gap-1 text-sm font-medium",
                          isDeployed
                            ? "text-foreground"
                            : "text-muted-foreground",
                        )}
                      >
                        <span
                          className={cn(
                            "h-2 w-2 rounded-full mr-1",
                            isDeployed
                              ? "bg-emerald-500"
                              : "bg-muted-foreground/60",
                          )}
                        />
                        {isDeployed ? "Deployed" : "Draft"}
                      </span>
                      <span className="text-muted-foreground">
                        {timeElapsed(entry.created_at)} ago
                      </span>
                    </button>
                    <span />
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}
