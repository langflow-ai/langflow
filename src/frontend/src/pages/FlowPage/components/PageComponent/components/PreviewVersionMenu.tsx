import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createPortal } from "react-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import {
  useDeleteHistoryEntry,
  useGetFlowHistory,
} from "@/controllers/API/queries/flow-history";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useHistoryPreviewStore from "@/stores/historyPreviewStore";
import {
  downloadFlow,
  processFlows,
  removeApiKeys,
} from "@/utils/reactflowUtils";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";

interface PreviewVersionMenuProps {
  historyId: string;
  versionTag: string;
  flowId: string;
}

export default function PreviewVersionMenu({
  historyId,
  versionTag,
  flowId,
}: PreviewVersionMenuProps) {
  const queryClient = useQueryClient();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);
  const applyFlowToCanvas = useApplyFlowToCanvas();
  const clearPreview = useHistoryPreviewStore((s) => s.clearPreview);
  const setPreview = useHistoryPreviewStore((s) => s.setPreview);
  const currentFlow = useFlowStore((s) => s.currentFlow);
  const originalStoreRef_nodes = useFlowStore((s) => s.nodes);

  const { mutate: deleteEntry, isPending: isDeleting } =
    useDeleteHistoryEntry();

  const { data: historyResponse } = useGetFlowHistory({ flowId });

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const handleRestore = async () => {
    setShowRestoreConfirm(false);
    setIsRestoring(true);
    try {
      const response = await api.post(
        `${getURL("FLOWS")}/${flowId}/history/${historyId}/activate`,
        null,
        { params: { save_draft: true } },
      );
      const updatedFlow = response.data;
      queryClient.invalidateQueries({ queryKey: ["useGetFlowHistory"] });
      const flow = {
        ...updatedFlow,
        data: {
          nodes: updatedFlow.data?.nodes ?? [],
          edges: updatedFlow.data?.edges ?? [],
        },
      };
      processFlows([flow]);
      applyFlowToCanvas(flow);
      clearPreview();
      setSuccessData({ title: "Version restored" });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setErrorData({
        title: "Failed to restore version",
        ...(detail ? { list: [detail] } : {}),
      });
    } finally {
      setIsRestoring(false);
    }
  };

  const handleExport = async () => {
    try {
      const response = await api.get(
        `${getURL("FLOWS")}/${flowId}/history/${historyId}`,
      );
      const data = response.data?.data;
      const tag = response.data?.version_tag ?? "version";
      if (!data) {
        setErrorData({ title: "No data available to export" });
        return;
      }
      const flowName = `${currentFlow?.name || "flow"}_${tag}`;
      const flowToExport = removeApiKeys({
        id: currentFlow?.id ?? "",
        data,
        name: flowName,
        description: currentFlow?.description ?? "",
        is_component: false,
      } as any);
      downloadFlow(flowToExport, flowName);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setErrorData({
        title: "Failed to export version",
        ...(detail ? { list: [detail] } : {}),
      });
    }
  };

  const handleDelete = () => {
    setShowDeleteConfirm(false);
    const entries = historyResponse?.entries ?? [];
    const currentIndex = entries.findIndex((e) => e.id === historyId);
    const nextEntry =
      currentIndex > 0 ? entries[currentIndex - 1] : entries[currentIndex + 1];
    deleteEntry(
      { flowId, historyId },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ["useGetFlowHistory"] });
          setSuccessData({ title: "Version deleted" });
          if (nextEntry) {
            setPreview([], [], nextEntry.version_tag, nextEntry.id);
          } else {
            clearPreview();
          }
        },
        onError: (err: any) => {
          const detail = err?.response?.data?.detail;
          setErrorData({
            title: "Failed to delete version",
            ...(detail ? { list: [detail] } : {}),
          });
        },
      },
    );
  };

  return (
    <>
      <DropdownMenu onOpenChange={setIsOpen}>
        <DropdownMenuTrigger asChild>
          <button className="flex items-center rounded text-accent-indigo-foreground transition-colors hover:text-accent-indigo-foreground">
            <ForwardedIconComponent
              name="ChevronDown"
              className={`h-3.5 w-3.5 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
            />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side="bottom"
          align="center"
          className="w-44 border-accent-indigo-foreground text-accent-indigo-foreground backdrop-blur-sm bg-transparent"
        >
          <DropdownMenuItem
            onClick={() => setShowRestoreConfirm(true)}
            disabled={isRestoring}
            className="cursor-pointer text-accent-indigo-foreground focus:bg-accent-indigo focus:text-accent-indigo-foreground"
          >
            <ForwardedIconComponent
              name="RotateCcw"
              className="mr-2 h-3.5 w-3.5"
            />
            Restore
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={handleExport}
            className="cursor-pointer text-accent-indigo-foreground focus:bg-accent-indigo focus:text-accent-indigo-foreground"
          >
            <ForwardedIconComponent
              name="Download"
              className="mr-2 h-3.5 w-3.5"
            />
            Export
          </DropdownMenuItem>
          <DropdownMenuSeparator className="bg-accent-indigo-foreground" />
          <DropdownMenuItem
            onClick={() => setShowDeleteConfirm(true)}
            className="cursor-pointer text-destructive focus:bg-destructive/20 focus:text-destructive"
          >
            <ForwardedIconComponent
              name="Trash2"
              className="mr-2 h-3.5 w-3.5"
            />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Restore confirmation */}
      {showRestoreConfirm &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg">
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  name="RotateCcw"
                  className="h-5 w-5 text-primary"
                />
                <span className="text-lg font-semibold">Restore Version</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Restore <strong>{versionTag}</strong>? Your current draft will
                be saved before restoring.
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowRestoreConfirm(false)}
                >
                  Cancel
                </Button>
                <Button size="sm" onClick={handleRestore} loading={isRestoring}>
                  Restore
                </Button>
              </div>
            </div>
          </div>,
          document.body,
        )}

      {/* Delete confirmation */}
      {showDeleteConfirm &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg">
              <div className="flex items-center gap-2">
                <ForwardedIconComponent
                  name="Trash2"
                  className="h-5 w-5 text-destructive"
                />
                <span className="text-lg font-semibold">Delete Version</span>
              </div>
              <p className="text-sm text-muted-foreground">
                This will permanently delete <strong>{versionTag}</strong>. This
                can't be undone.
              </p>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDeleteConfirm(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleDelete}
                  loading={isDeleting}
                >
                  Delete
                </Button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
