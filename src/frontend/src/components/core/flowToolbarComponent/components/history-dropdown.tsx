import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { History, MoreHorizontal } from "lucide-react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useGetFlowVersionsQuery } from "@/controllers/API/queries/flows/use-get-flow-versions";
import { usePostRestoreFlowVersion } from "@/controllers/API/queries/flows/use-post-restore-flow-version";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import moment from "moment";
import { cn } from "@/utils/utils";

export default function HistoryDropdown() {
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const userData = useAuthStore((state) => state.userData);
  const currentFlowId = currentFlow?.id;
  const { data: versions, isLoading } = useGetFlowVersionsQuery({ flowId: currentFlowId });
  const { mutate: restoreVersion, isPending } = usePostRestoreFlowVersion();
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const handleRestore = (versionId: string) => {
    if (!currentFlowId) return;
    restoreVersion(
      { flowId: currentFlowId, versionId },
      {
        onSuccess: () => {
          setSuccessData({ title: "Version restored successfully" });
        },
        onError: () => {
          setErrorData({ title: "Error restoring version" });
        },
      }
    );
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button 
          variant="ghost" 
          size="icon" 
          className="h-9 w-9"
          data-testid="flow-history-button"
          disabled={!currentFlowId}
        >
          <History className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-72" align="end">
        <DropdownMenuLabel className="text-sm font-semibold">Version History</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="max-h-[350px] overflow-y-auto py-1">
          {isLoading ? (
            <div className="p-4 text-center text-sm text-muted-foreground">Loading...</div>
          ) : !versions || versions.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">No history available</div>
          ) : (
            versions.map((version, index) => {
              // Handle nested FlowVersion structure from backend
              const versionData = version.FlowVersion || version;
              const isLatest = index === 0;
              
              return (
                <div 
                  key={versionData.id} 
                  className={cn(
                    "relative flex items-start justify-between px-3 py-2.5 mx-1 rounded-md group transition-colors",
                    "hover:bg-accent/60",
                    isLatest && "border-l-2 border-primary bg-accent/30"
                  )}
                >
                  <div className="flex flex-col gap-0.5 min-w-0 flex-1 pr-2">
                    <span
                      className={cn(
                        isLatest
                          ? "text-sm font-medium text-foreground"
                          : "text-xs text-muted-foreground"
                      )}
                    >
                      {isLatest
                        ? "Latest Version"
                        : moment
                            .utc(versionData.created_at)
                            .local()
                            .format("MMM D, h:mm A")}
                    </span>
                    {isLatest ? (
                      <>
                        <span className="text-xs text-muted-foreground">
                          Saved{" "}
                          {moment
                            .utc(versionData.created_at)
                            .local()
                            .format("MMM D")}{" "}
                          at{" "}
                          {moment
                            .utc(versionData.created_at)
                            .local()
                            .format("h:mm A")}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {userData?.username ?? "Unknown"}
                        </span>
                      </>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        {userData?.username ?? "Unknown"}
                      </span>
                    )}
                  </div>
                  
                  {!isLatest && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="h-7 w-7 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" side="left">
                        <DropdownMenuItem 
                          onClick={() => handleRestore(versionData.id)}
                          disabled={isPending}
                        >
                          Restore this version
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>
              );
            })
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
