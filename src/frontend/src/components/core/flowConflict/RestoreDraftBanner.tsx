import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { raiseConflictForStaleWork } from "@/hooks/flows/use-check-flow-version";
import useAuthStore from "@/stores/authStore";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";
import {
  type ConflictDraft,
  clearConflictDraft,
  readConflictDraft,
} from "@/utils/conflict-draft";

/**
 * Offers back work that a refused save left stranded in a closed tab.
 *
 * An offer rather than an automatic restore: applying it silently would resurrect
 * work someone may have walked away from on purpose, and drop them straight back
 * into a conflict they never chose to re-enter.
 */
export function RestoreDraftBanner({ flowId }: { flowId: string }) {
  const { t } = useTranslation();
  const userId = useAuthStore((state) => state.userData?.id);
  const conflict = useFlowConflictStore((state) => state.conflict);
  const setNodes = useFlowStore((state) => state.setNodes);
  const setEdges = useFlowStore((state) => state.setEdges);
  const previewingVersion = useVersionPreviewStore(
    (state) => state.previewLabel !== null,
  );
  const [draft, setDraft] = useState<ConflictDraft | null>(null);

  useEffect(() => {
    setDraft(readConflictDraft(userId, flowId));
  }, [userId, flowId]);

  // One banner at a time: a live conflict is the more urgent of the two, and both
  // of them sit in the same place at the bottom of the canvas.
  if (!draft || conflict?.flowId === flowId || previewingVersion) return null;

  const savedAt = new Date(draft.savedAt).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  const restore = () => {
    // Applied without saving: it was refused once already, and saving now would
    // overwrite the very person the refusal protected.
    setNodes(draft.data?.nodes ?? [], { autoSave: false });
    setEdges(draft.data?.edges ?? [], { autoSave: false });
    // But it *is* unsaved work of the user's. Without saying so, nothing treats
    // it as theirs — and a later run would adopt the server's version straight
    // over the top of what was just restored.
    useFlowStore.setState({ userEditedSinceLoad: true });
    void raiseConflictForStaleWork(flowId, draft.versionToken, userId ?? null);
    clearConflictDraft(userId, flowId);
    setDraft(null);
  };

  const discard = () => {
    clearConflictDraft(userId, flowId);
    setDraft(null);
  };

  return (
    <div
      className="pointer-events-none absolute inset-x-0 bottom-6 z-50 flex justify-center px-6"
      data-testid="restore-draft-banner"
    >
      <div
        role="status"
        className="pointer-events-auto flex w-full max-w-3xl items-center gap-4 rounded-xl border border-border bg-background px-5 py-4 shadow-lg"
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
          <ForwardedIconComponent
            name="History"
            className="h-5 w-5 text-muted-foreground"
            aria-hidden="true"
          />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">
            {t("multiEdit.draft.title", { time: savedAt })}
          </p>
          <p className="text-mmd text-muted-foreground">
            {draft.secretsCleared
              ? t("multiEdit.draft.descriptionScrubbed")
              : t("multiEdit.draft.description")}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={discard}>
            {t("multiEdit.draft.discard")}
          </Button>
          <Button
            size="sm"
            onClick={restore}
            data-testid="restore-draft-button"
          >
            {t("multiEdit.draft.restore")}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default RestoreDraftBanner;
