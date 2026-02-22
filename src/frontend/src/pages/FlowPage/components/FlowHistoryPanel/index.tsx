import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  useDeleteHistoryEntry,
  useGetFlowHistory,
  usePostActivateVersion,
  usePostCreateSnapshot,
} from "@/controllers/API/queries/flow-history";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowHistoryEntry, FlowHistoryEntryFull } from "@/types/flow/history";
import { useCallback, useState } from "react";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import FlowHistoryPreview from "../FlowHistoryPreview";

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function StateBadge({ state }: { state: FlowHistoryEntry["state"] }) {
  if (state === "PUBLISHED") {
    return (
      <Badge variant="successStatic" size="sm">
        Active
      </Badge>
    );
  }
  if (state === "ARCHIVED") {
    return (
      <Badge variant="secondaryStatic" size="sm">
        Archived
      </Badge>
    );
  }
  return (
    <Badge variant="gray" size="sm">
      Draft
    </Badge>
  );
}

interface FlowHistoryPanelProps {
  flowId: string;
  onClose: () => void;
}

export default function FlowHistoryPanel({
  flowId,
  onClose,
}: FlowHistoryPanelProps) {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);

  const [description, setDescription] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [confirmActivateId, setConfirmActivateId] = useState<string | null>(
    null,
  );
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [previewEntry, setPreviewEntry] = useState<FlowHistoryEntryFull | null>(
    null,
  );
  const [loadingPreviewId, setLoadingPreviewId] = useState<string | null>(null);

  const { data: history, isLoading } = useGetFlowHistory(
    { flowId },
    { refetchInterval: 10000 },
  );

  const { mutate: createSnapshot, isPending: isCreating } =
    usePostCreateSnapshot();
  const { mutate: activateVersion, isPending: isActivating } =
    usePostActivateVersion();
  const { mutate: deleteEntry, isPending: isDeleting } =
    useDeleteHistoryEntry();

  const currentFlow = useFlowStore((state) => state.currentFlow);
  const activeVersionId = currentFlow?.active_version_id;

  const handleCreateSnapshot = useCallback(() => {
    createSnapshot(
      { flowId, description: description || null },
      {
        onSuccess: () => {
          setSuccessData({ title: "Version saved" });
          setDescription("");
          setShowCreateForm(false);
        },
        onError: () => {
          setErrorData({ title: "Failed to save version" });
        },
      },
    );
  }, [flowId, description, createSnapshot, setSuccessData, setErrorData]);

  const handleActivate = useCallback(
    (historyId: string) => {
      activateVersion(
        { flowId, historyId },
        {
          onSuccess: (updatedFlow) => {
            setSuccessData({ title: "Version activated" });
            setCurrentFlow(updatedFlow);
            setConfirmActivateId(null);
          },
          onError: () => {
            setErrorData({ title: "Failed to activate version" });
            setConfirmActivateId(null);
          },
        },
      );
    },
    [
      flowId,
      activateVersion,
      setSuccessData,
      setErrorData,
      setCurrentFlow,
    ],
  );

  const handleDelete = useCallback(
    (historyId: string) => {
      deleteEntry(
        { flowId, historyId },
        {
          onSuccess: () => {
            setSuccessData({ title: "Version deleted" });
            setConfirmDeleteId(null);
          },
          onError: () => {
            setErrorData({ title: "Failed to delete version" });
            setConfirmDeleteId(null);
          },
        },
      );
    },
    [flowId, deleteEntry, setSuccessData, setErrorData],
  );

  const handlePreview = useCallback(
    async (entryId: string) => {
      setLoadingPreviewId(entryId);
      try {
        const response = await api.get<FlowHistoryEntryFull>(
          `${getURL("FLOWS")}/${flowId}/history/${entryId}`,
        );
        setPreviewEntry(response.data);
      } catch {
        setErrorData({ title: "Failed to load version preview" });
      } finally {
        setLoadingPreviewId(null);
      }
    },
    [flowId, setErrorData],
  );

  const handlePreviewActivate = useCallback(
    (historyId: string) => {
      activateVersion(
        { flowId, historyId },
        {
          onSuccess: (updatedFlow) => {
            setSuccessData({ title: "Version activated" });
            setCurrentFlow(updatedFlow);
            setPreviewEntry(null);
          },
          onError: () => {
            setErrorData({ title: "Failed to activate version" });
          },
        },
      );
    },
    [flowId, activateVersion, setSuccessData, setErrorData, setCurrentFlow],
  );

  if (previewEntry) {
    return (
      <FlowHistoryPreview
        historyEntry={previewEntry}
        onClose={() => setPreviewEntry(null)}
        onActivate={handlePreviewActivate}
        isActivating={isActivating}
      />
    );
  }

  return (
    <div className="flex h-full w-80 flex-col border-l bg-background">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <ForwardedIconComponent name="History" className="h-4 w-4" />
          <span className="text-sm font-semibold">Version History</span>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>

      {/* Save Version */}
      <div className="border-b px-4 py-3">
        {showCreateForm ? (
          <div className="flex flex-col gap-2">
            <input
              type="text"
              placeholder="Version description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="h-8 rounded-md border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreateSnapshot();
                if (e.key === "Escape") setShowCreateForm(false);
              }}
              autoFocus
            />
            <div className="flex gap-2">
              <Button
                variant="default"
                size="xs"
                onClick={handleCreateSnapshot}
                loading={isCreating}
                className="flex-1"
              >
                Save
              </Button>
              <Button
                variant="outline"
                size="xs"
                onClick={() => setShowCreateForm(false)}
                className="flex-1"
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button
            variant="primary"
            size="sm"
            onClick={() => setShowCreateForm(true)}
            className="w-full"
          >
            <ForwardedIconComponent name="Save" className="h-4 w-4" />
            <span>Save Version</span>
          </Button>
        )}
      </div>

      {/* History list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <ForwardedIconComponent
              name="Loader2"
              className="h-5 w-5 animate-spin text-muted-foreground"
            />
          </div>
        )}
        {!isLoading && (!history || history.length === 0) && (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            No versions saved yet
          </div>
        )}
        {history?.map((entry) => {
          const isActive = entry.id === activeVersionId;
          return (
            <div
              key={entry.id}
              className={`border-b px-4 py-3 ${isActive ? "bg-accent/30" : ""}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">
                    {entry.version_tag}
                  </span>
                  <StateBadge state={entry.state} />
                </div>
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(entry.created_at)}
                </span>
              </div>
              {entry.description && (
                <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                  {entry.description}
                </p>
              )}
              <div className="mt-2 flex gap-1">
                {/* Confirm Activate */}
                {confirmActivateId === entry.id ? (
                  <div className="flex w-full items-center gap-1">
                    <span className="text-xs text-muted-foreground">
                      Activate?
                    </span>
                    <Button
                      variant="default"
                      size="xs"
                      onClick={() => handleActivate(entry.id)}
                      loading={isActivating}
                    >
                      Yes
                    </Button>
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => setConfirmActivateId(null)}
                    >
                      No
                    </Button>
                  </div>
                ) : confirmDeleteId === entry.id ? (
                  <div className="flex w-full items-center gap-1">
                    <span className="text-xs text-muted-foreground">
                      Delete?
                    </span>
                    <Button
                      variant="destructive"
                      size="xs"
                      onClick={() => handleDelete(entry.id)}
                      loading={isDeleting}
                    >
                      Yes
                    </Button>
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => setConfirmDeleteId(null)}
                    >
                      No
                    </Button>
                  </div>
                ) : (
                  <>
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => handlePreview(entry.id)}
                      loading={loadingPreviewId === entry.id}
                    >
                      <ForwardedIconComponent
                        name="Eye"
                        className="mr-1 h-3 w-3"
                      />
                      Preview
                    </Button>
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => setConfirmActivateId(entry.id)}
                      disabled={isActive}
                    >
                      <ForwardedIconComponent
                        name="RotateCcw"
                        className="mr-1 h-3 w-3"
                      />
                      Activate
                    </Button>
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => setConfirmDeleteId(entry.id)}
                      disabled={isActive}
                    >
                      <ForwardedIconComponent
                        name="Trash2"
                        className="mr-1 h-3 w-3"
                      />
                    </Button>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
