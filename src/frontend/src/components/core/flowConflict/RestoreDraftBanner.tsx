import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
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
import { CanvasBanner } from "./CanvasBanner";

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

  const restore = async () => {
    // Applied without saving: it was refused once already, and saving now would
    // overwrite the very person the refusal protected.
    setNodes(draft.data?.nodes ?? [], { autoSave: false });
    setEdges(draft.data?.edges ?? [], { autoSave: false });
    // But it *is* unsaved work of the user's. Without saying so, nothing treats
    // it as theirs — and a later run would adopt the server's version straight
    // over the top of what was just restored.
    useFlowStore.setState({ userEditedSinceLoad: true });
    setDraft(null);

    // The stored copy is dropped only when the restored work is no longer at
    // risk. Clearing it unconditionally disarmed the protection at the very
    // moment it was needed again: the work was back on the canvas, unsaved, in
    // conflict, and a second reload lost it for good.
    const stillInConflict = await raiseConflictForStaleWork(
      flowId,
      draft.versionToken,
      userId ?? null,
    );
    if (!stillInConflict) clearConflictDraft(userId, flowId);
  };

  const discard = () => {
    clearConflictDraft(userId, flowId);
    setDraft(null);
  };

  return (
    <CanvasBanner
      testId="restore-draft-banner"
      tone="neutral"
      icon="History"
      title={t("multiEdit.draft.title", { time: savedAt })}
      description={
        draft.secretsCleared
          ? t("multiEdit.draft.descriptionScrubbed")
          : t("multiEdit.draft.description")
      }
      actions={
        <>
          <Button variant="conflictSecondary" size="banner" onClick={discard}>
            {t("multiEdit.draft.discard")}
          </Button>
          <Button
            variant="conflictPrimary"
            size="banner"
            onClick={() => void restore()}
            data-testid="restore-draft-button"
          >
            {t("multiEdit.draft.restore")}
          </Button>
        </>
      }
    />
  );
}

export default RestoreDraftBanner;
