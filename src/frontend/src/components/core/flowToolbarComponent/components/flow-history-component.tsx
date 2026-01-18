import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useGetFlowHistory } from "@/controllers/API/queries/flow-history/use-get-flow-history";
import { useGetFlowVersion } from "@/controllers/API/queries/flow-history/use-get-flow-version";
import { usePostFlowHistory } from "@/controllers/API/queries/flow-history/use-post-flow-history";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import {
  Copy,
  Download,
  GitBranchPlus,
  History,
  MoreVertical,
  RotateCcw,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePostAddFlow } from "@/controllers/API/queries/flows/use-post-add-flow";
import { customOpenNewTab } from "@/customization/utils/custom-open-new-tab";
import { createNewFlow, downloadFlow } from "@/utils/reactflowUtils";

export default function FlowHistoryComponent() {
  const [open, setOpen] = useState(false);
  const [rangeFilter, setRangeFilter] = useState<"all" | "day" | "week">(
    "all",
  );
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: history, refetch: refetchHistory } = useGetFlowHistory({
    flowId: currentFlow?.id || "",
  });
  const { mutateAsync: createCheckpoint } = usePostFlowHistory();
  const { mutateAsync: getVersion } = useGetFlowVersion();
  const { mutateAsync: postAddFlow } = usePostAddFlow();

  const handleCheckpoint = async () => {
    if (!currentFlow) return;

    try {
      const currentFlowData = {
        ...currentFlow,
        data: {
          ...currentFlow.data,
          nodes,
          edges,
        },
      };

      await createCheckpoint({
        flowId: currentFlow.id,
        data: currentFlowData,
      });

      setSuccessData({ title: "Checkpoint created" });
      refetchHistory();
    } catch (error) {
      console.error("Failed to create checkpoint:", error);
      setErrorData({
        title: "Failed to create checkpoint",
        list: ["An error occurred while creating the checkpoint."],
      });
    }
  };

  const handleRestore = async (versionId: string) => {
    if (!currentFlow) return;

    try {
      // 1. SAFETY STEP: Save current state as a new checkpoint
      const currentFlowData = {
        ...currentFlow,
        data: {
          ...currentFlow.data,
          nodes,
          edges,
        },
      };

      await createCheckpoint({
        flowId: currentFlow.id,
        data: currentFlowData,
      });

      // 2. Fetch the historical version
      const versionData = await getVersion({
        flowId: currentFlow.id,
        versionId,
      });

      // 3. Update the store (Restore)
      if (versionData?.flow_data) {
        setNodes(versionData.flow_data.nodes);
        setEdges(versionData.flow_data.edges);
        setSuccessData({ title: "Restored to previous version" });
        setOpen(false);
        // Refresh history to show the auto-saved checkpoint
        refetchHistory();
      }
    } catch (error) {
      console.error("Failed to restore version:", error);
      setErrorData({
        title: "Failed to restore version",
        list: ["An error occurred while restoring the flow version."],
      });
    }
  };

  const handleCloneVersion = async (versionId: string) => {
    if (!currentFlow) return;

    try {
      const versionData = await getVersion({
        flowId: currentFlow.id,
        versionId,
      });

      if (!versionData?.flow_data) return;

      const viewport =
        versionData.flow_data.viewport ??
        currentFlow.data?.viewport ?? { x: 0, y: 0, zoom: 1 };
      const flowData = {
        nodes: versionData.flow_data.nodes,
        edges: versionData.flow_data.edges,
        viewport,
      };
      const folderId = currentFlow.folder_id ?? "";
      const newFlow = createNewFlow(flowData, folderId, currentFlow);

      const createdFlow = await postAddFlow(newFlow);
      if (createdFlow?.id) {
        const folderPath = createdFlow.folder_id
          ? `/folder/${createdFlow.folder_id}`
          : "";
        customOpenNewTab(`/flow/${createdFlow.id}${folderPath}`);
      }
      setSuccessData({ title: "Flow cloned from version" });
      setOpen(false);
    } catch (error) {
      console.error("Failed to clone version:", error);
      setErrorData({
        title: "Failed to clone version",
        list: ["An error occurred while cloning the flow version."],
      });
    }
  };

  const handleDownloadVersion = async (versionId: string) => {
    if (!currentFlow) return;

    try {
      const versionData = await getVersion({
        flowId: currentFlow.id,
        versionId,
      });

      if (!versionData?.flow_data) return;

      const nodes = versionData.flow_data.nodes ?? [];
      const edges = versionData.flow_data.edges ?? [];
      const viewport =
        versionData.flow_data.viewport ??
        currentFlow.data?.viewport ?? { x: 0, y: 0, zoom: 1 };
      const flowForDownload = {
        ...currentFlow,
        data: {
          nodes,
          edges,
          viewport,
        },
      };

      await downloadFlow(
        flowForDownload,
        currentFlow.name,
        currentFlow.description,
      );
      setSuccessData({ title: "Version downloaded" });
    } catch (error) {
      console.error("Failed to download version:", error);
      setErrorData({
        title: "Failed to download version",
        list: ["An error occurred while downloading the flow version."],
      });
    }
  };

  const historyItems = useMemo(
    () => history?.flow_history ?? [],
    [history?.flow_history],
  );
  const sortedHistory = useMemo(
    () =>
      [...historyItems].sort(
        (a, b) =>
          new Date(b.created_at).getTime() -
          new Date(a.created_at).getTime(),
      ),
    [historyItems],
  );
  const filteredHistory = useMemo(() => {
    if (rangeFilter === "all") return sortedHistory;
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - (rangeFilter === "day" ? 1 : 7));
    return sortedHistory.filter(
      (item) => new Date(item.created_at) >= cutoff,
    );
  }, [rangeFilter, sortedHistory]);

  const hasHistory = historyItems.length > 0;
  const hasFilteredHistory = filteredHistory.length > 0;
  const rangeButtonClass = (value: "all" | "day" | "week") =>
    `h-7 w-full justify-center rounded-sm px-2 text-[11px] transition ${
      rangeFilter === value
        ? "bg-background text-foreground shadow-sm"
        : "text-muted-foreground hover:text-foreground"
    }`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 border-none hover:bg-muted focus:ring-0"
          title="Flow History"
          data-testid="flow-history-button"
        >
          <History className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-80 p-0"
        align="end"
        alignOffset={-2}
        side="bottom"
        sideOffset={7}
      >
        <div className="border-b p-3">
          <div className="flex items-center justify-between">
            <div className="font-medium">Flow History</div>
            {hasHistory && (
              <Button
                onClick={handleCheckpoint}
                variant="ghost"
                size="sm"
                className="h-8 gap-2 px-2 text-xs"
                title="Create Checkpoint"
              >
                <GitBranchPlus className="h-3.5 w-3.5" />
                Checkpoint
              </Button>
            )}
          </div>
          <div className="mt-3 grid grid-cols-3 gap-1 rounded-md border bg-muted/50 p-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={rangeButtonClass("all")}
              onClick={() => setRangeFilter("all")}
              aria-pressed={rangeFilter === "all"}
            >
              All
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={rangeButtonClass("day")}
              onClick={() => setRangeFilter("day")}
              aria-pressed={rangeFilter === "day"}
            >
              24h
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={rangeButtonClass("week")}
              onClick={() => setRangeFilter("week")}
              aria-pressed={rangeFilter === "week"}
            >
              7d
            </Button>
          </div>
        </div>

        <div className="max-h-[400px] space-y-1 overflow-y-auto p-2">
          {!hasHistory ? (
            <div className="flex h-20 flex-col items-center justify-center gap-4 p-3 text-center text-sm text-muted-foreground">
              <Button
                onClick={handleCheckpoint}
                variant="outline"
                size="sm"
                className="w-full gap-2"
              >
                <GitBranchPlus className="h-4 w-4" />
                Create First Checkpoint
              </Button>
            </div>
          ) : !hasFilteredHistory ? (
            <div className="flex h-20 flex-col items-center justify-center gap-3 p-3 text-center text-sm text-muted-foreground">
              <span>No checkpoints in this range.</span>
              <Button
                onClick={handleCheckpoint}
                variant="outline"
                size="sm"
                className="w-full gap-2"
              >
                <GitBranchPlus className="h-4 w-4" />
                Create Checkpoint
              </Button>
            </div>
          ) : (
            filteredHistory.map((item) => (
              <div
                key={item.id}
                className="group flex flex-col border-b px-3 py-2 text-sm last:border-b-0 hover:bg-muted/50"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex flex-col">
                    <span className="font-medium leading-none">
                      {new Date(item.created_at).toLocaleDateString("en-US")} at{" "}
                      {new Date(item.created_at).toLocaleTimeString("en-US")}
                    </span>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-muted-foreground opacity-100 transition hover:text-foreground focus-visible:opacity-100 group-hover:opacity-100 sm:opacity-0"
                        aria-label="History actions"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem
                        className="gap-2"
                        onClick={() => handleRestore(item.id)}
                      >
                        <RotateCcw className="h-4 w-4" />
                        Restore
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="gap-2"
                        onClick={() => handleCloneVersion(item.id)}
                      >
                        <Copy className="h-4 w-4" />
                        Clone to new flow
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="gap-2"
                        onClick={() => handleDownloadVersion(item.id)}
                      >
                        <Download className="h-4 w-4" />
                        Download
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
