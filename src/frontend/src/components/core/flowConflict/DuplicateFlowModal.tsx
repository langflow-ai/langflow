import type { AxiosError } from "axios";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { usePostCreateSnapshot } from "@/controllers/API/queries/flow-version/use-post-create-snapshot";
import { usePostForkFlow } from "@/controllers/API/queries/flows/use-post-fork-flow";
import { usePostOverwriteFlow } from "@/controllers/API/queries/flows/use-post-overwrite-flow";
import { adoptServerVersionOnCanvas } from "@/hooks/flows/adopt-version-on-canvas";
import {
  attachTheirFlow,
  fetchAndAdoptServerVersion,
  refreshConflictState,
} from "@/hooks/flows/conflict-actions";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { clearConflictDraft } from "@/utils/conflict-draft";
import {
  applySelectedChanges,
  contestedTargetKeys,
  diffGraphs,
  groupChangesByTarget,
  siblingChangeIds,
} from "@/utils/flow-diff";
import ChangeRow from "./ChangeRow";
import ConflictDialogFooter from "./ConflictDialogFooter";

/** The shape the server sends back when it refuses a write. */
type OverwriteRefusal = {
  code?: string;
  expected_version_token?: string | null;
  current_version_token?: string | null;
  modified_at?: string | null;
  modified_by?: { id?: string | null; username?: string | null } | null;
};

/**
 * Chooses what leaves a conflict, and where it lands.
 *
 * The author's own work is never optional — it is the reason they are here — so it
 * is listed for confidence, not for choice. Only the other person's changes are
 * selectable, and only where taking one cannot silently overwrite the author's own
 * edit to the same component.
 *
 * The same selection feeds both exits. Duplicating puts the result in a new flow
 * and leaves the original untouched; overwriting puts it in the original and files
 * the version it replaced into history, so the other person can still get it back.
 */
export function DuplicateFlowModal() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const conflict = useFlowConflictStore((state) => state.conflict);
  const dialogOpen = useFlowConflictStore((state) => state.dialogOpen);
  const closeDialog = useFlowConflictStore((state) => state.closeDialog);
  const openDialog = useFlowConflictStore((state) => state.openDialog);
  const abandonFlow = useFlowConflictStore((state) => state.abandonFlow);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const clearConflict = useFlowConflictStore((state) => state.clearConflict);
  const { mutateAsync: archiveMyVersion } = usePostCreateSnapshot();
  const { mutate: forkFlow, isPending: isForking } = usePostForkFlow();
  const { mutate: overwriteFlow, isPending: isOverwriting } =
    usePostOverwriteFlow();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Rebuilding after a refusal is asynchronous, and until it lands the dialog is
  // still describing the version that was just refused. Leaving the actions live
  // through it lets a second click resend the same stale token.
  const [isRebuilding, setIsRebuilding] = useState(false);
  // Discarding cannot be undone, so it is asked twice: the first click states
  // what will be lost, the second does it.
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);
  const [isDiscarding, setIsDiscarding] = useState(false);
  const isPending = isForking || isOverwriting || isRebuilding || isDiscarding;
  // `isPending` disables the buttons a render too late to stop a double click, and
  // the second fork then lost the race for the copy's name and came back an error.
  // A ref is the only guard that is already true inside the same click.
  const submittingRef = useRef(false);
  const claimSubmission = () => {
    if (submittingRef.current || isPending) return false;
    submittingRef.current = true;
    return true;
  };
  const releaseSubmission = () => {
    submittingRef.current = false;
  };

  const {
    theirChanges,
    myGroups,
    theirGroups,
    contested,
    myGraph,
    theirGraph,
  } = useMemo(() => {
    const baseFlow = useFlowsManagerStore.getState().currentFlow;
    const live = useFlowStore.getState();
    const base = baseFlow?.data ?? null;
    const mine = { nodes: live.nodes, edges: live.edges };
    const theirs = conflict?.theirFlow?.data ?? null;

    // Without the version we loaded there is no way to tell our edits from
    // theirs, so the dialog offers nothing to merge and still duplicates.
    const mineDiff = base ? diffGraphs(base, mine) : [];
    const theirsDiff = base && theirs ? diffGraphs(base, theirs) : [];

    return {
      myChanges: mineDiff,
      theirChanges: theirsDiff,
      // One row per component: it is adopted whole or not at all, so a row per
      // change offered checkboxes that could only ever move together.
      myGroups: groupChangesByTarget(mineDiff),
      theirGroups: groupChangesByTarget(theirsDiff),
      contested: contestedTargetKeys(mineDiff, theirsDiff),
      myGraph: mine,
      theirGraph: theirs,
    };
  }, [conflict?.theirFlow]);

  if (!conflict) return null;

  const authorName = conflict.author.username || t("multiEdit.unknownAuthor");

  // Components whose contested decision currently sits with them. My own changes
  // to those components are shown as replaced rather than quietly dropped.
  const takenFromThem = new Set(
    theirChanges
      .filter((change) => selected.has(change.id))
      .map((change) => change.targetKey),
  );
  const keptOfMine = myGroups.filter(
    (group) => !takenFromThem.has(group.targetKey),
  );
  const takenGroups = theirGroups.filter((group) =>
    takenFromThem.has(group.targetKey),
  );

  // Selecting one of their edits replaces the whole component, so its siblings
  // travel with it. Toggling them individually would apply changes nobody picked.
  const toggleComponent = (targetKey: string) =>
    setSelected((current) => {
      const next = new Set(current);
      const siblings = siblingChangeIds(theirChanges, targetKey);
      const isOn = siblings.some((id) => next.has(id));
      for (const id of siblings) {
        if (isOn) next.delete(id);
        else next.add(id);
      }
      return next;
    });

  const onDuplicate = () => {
    if (!claimSubmission()) return;
    forkFlow(
      { id: conflict.flowId, data: buildMerged() },
      {
        onSuccess: (created) => {
          // The work is now in a flow of its own, so the stranded copy has no
          // reason to be offered back the next time the source is opened.
          clearConflictDraft(
            useAuthStore.getState().userData?.id,
            conflict.flowId,
          );
          // Abandon rather than clear: the source keeps its stale token, so any
          // save still queued against it would only earn another refusal.
          abandonFlow(conflict.flowId);
          navigate(
            `/flow/${created.id}${created.folder_id ? `/folder/${created.folder_id}` : ""}`,
          );
        },
        onError: () => {
          releaseSubmission();
          setErrorData({ title: t("multiEdit.dialog.duplicateFailed") });
        },
      },
    );
  };

  const buildMerged = () => {
    const merged = applySelectedChanges(
      myGraph,
      theirGraph,
      theirChanges,
      selected,
    );
    const viewport = useFlowStore
      .getState()
      .reactFlowInstance?.getViewport() ?? { x: 0, y: 0, zoom: 1 };
    return { ...merged, viewport };
  };

  /**
   * Leaves the conflict by giving up your own edits and taking the server's version.
   *
   * The exit the kickoff called "discard and take the latest" and the only one
   * that asks for nothing in return: without it, someone who just wants their
   * colleague's version has to duplicate a flow they do not want, and cannot
   * leave the page while the conflict stands.
   */
  /** The canvas exactly as this person left it, read at the moment they leave. */
  const captureMyCanvas = () => {
    const live = useFlowStore.getState();
    return {
      nodes: live.nodes,
      edges: live.edges,
      viewport: live.reactFlowInstance?.getViewport() ?? {
        x: 0,
        y: 0,
        zoom: 1,
      },
    } as unknown as Record<string, unknown>;
  };

  const onDiscard = async () => {
    if (!claimSubmission()) return;
    setIsDiscarding(true);
    try {
      // Archived before anything is thrown away, and the discard is abandoned
      // if it cannot be: the button promises this work stays recoverable, and a
      // discard that silently failed to keep that promise is the one outcome
      // this dialog exists to prevent.
      try {
        await archiveMyVersion({
          flowId: conflict.flowId,
          description: t("multiEdit.dialog.discardArchiveLabel"),
          data: captureMyCanvas(),
        });
      } catch {
        setErrorData({ title: t("multiEdit.dialog.discardArchiveFailed") });
        return;
      }

      const adopted = await fetchAndAdoptServerVersion(conflict.flowId);
      if (!adopted) {
        setErrorData({ title: t("multiEdit.dialog.overwriteFailed") });
        return;
      }
      // Safe to drop now: the same work is in version history.
      clearConflictDraft(useAuthStore.getState().userData?.id, conflict.flowId);
      clearConflict();
      setSuccessData({ title: t("multiEdit.dialog.discardSucceeded") });
    } finally {
      setIsDiscarding(false);
      releaseSubmission();
      setConfirmingDiscard(false);
    }
  };

  const onOverwrite = () => {
    if (!conflict.currentToken) {
      setErrorData({ title: t("multiEdit.dialog.overwriteFailed") });
      return;
    }
    if (!claimSubmission()) return;
    overwriteFlow(
      {
        id: conflict.flowId,
        data: buildMerged(),
        // The version shown in this dialog. If the flow moved again while it was
        // open the server refuses, rather than discarding whoever moved it.
        reviewedVersionToken: conflict.currentToken,
      },
      {
        onSuccess: (updated) => {
          releaseSubmission();
          clearConflictDraft(
            useAuthStore.getState().userData?.id,
            conflict.flowId,
          );
          // Onto the canvas too, not just the baseline: whatever was taken from
          // them is part of the flow now and has to be what the person sees.
          adoptServerVersionOnCanvas(updated);
          clearConflict();
          setSuccessData({ title: t("multiEdit.dialog.overwriteSucceeded") });
        },
        onError: (error) => {
          releaseSubmission();
          void handleOverwriteRefusal(error);
        },
      },
    );
  };

  /**
   * Rebuilds the dialog when the flow moved again while it was open.
   *
   * A toast alone left the person stuck: the refusal is correct, but the diff on
   * screen still described the version they were refused against, so cancelling
   * and reopening showed the same stale comparison and overwriting again would
   * only be refused again.
   */
  const handleOverwriteRefusal = async (error: AxiosError) => {
    const refusal = error.response?.data as
      | { detail?: OverwriteRefusal }
      | undefined;
    const detail = refusal?.detail;
    if (
      error.response?.status !== 409 ||
      detail?.code !== "flow_version_conflict"
    ) {
      setErrorData({ title: t("multiEdit.dialog.overwriteFailed") });
      return;
    }
    setIsRebuilding(true);
    refreshConflictState({
      flowId: conflict.flowId,
      authorId: detail.modified_by?.id ?? null,
      authorName: detail.modified_by?.username ?? null,
      modifiedAt: detail.modified_at ?? null,
      expectedToken: detail.expected_version_token ?? null,
      currentToken: detail.current_version_token ?? null,
      currentUserId: useAuthStore.getState().userData?.id ?? null,
    });
    try {
      await attachTheirFlow(conflict.flowId);
    } finally {
      setIsRebuilding(false);
    }
    setSelected(new Set());
    openDialog();
    setErrorData({ title: t("multiEdit.dialog.overwriteMovedAgain") });
  };

  const footer =
    takenFromThem.size > 0
      ? t("multiEdit.dialog.footerBoth", {
          yours: keptOfMine.length,
          theirs: takenGroups.length,
        })
      : t("multiEdit.dialog.footerYours", { count: myGroups.length });

  return (
    <Dialog open={dialogOpen} onOpenChange={(open) => !open && closeDialog()}>
      <DialogContent className="max-w-2xl" data-testid="duplicate-flow-modal">
        <DialogHeader>
          <DialogTitle>{t("multiEdit.dialog.title")}</DialogTitle>
          <DialogDescription>
            {t("multiEdit.dialog.subtitle", { name: authorName })}
          </DialogDescription>
        </DialogHeader>

        {/* Padded on every side the scroll box clips: without the bottom, the last
            row's border sits exactly on the overflow edge and is shaved off. */}
        <div className="max-h-[55vh] space-y-6 overflow-y-auto px-1 pb-1">
          <section>
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("multiEdit.dialog.yourChanges")}
              </h3>
              <span className="flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground">
                <ForwardedIconComponent
                  name="Lock"
                  className="h-3 w-3"
                  aria-hidden="true"
                />
                {takenFromThem.size > 0
                  ? t("multiEdit.dialog.includedUnlessReplaced")
                  : t("multiEdit.dialog.alwaysIncluded")}
              </span>
            </div>
            {myGroups.length === 0 ? (
              <p className="text-mmd text-muted-foreground">
                {t("multiEdit.dialog.noYourChanges")}
              </p>
            ) : (
              <div className="space-y-2">
                {myGroups.map((group) => {
                  const replaced = takenFromThem.has(group.targetKey);
                  return (
                    <ChangeRow
                      key={group.targetKey}
                      group={group}
                      side="mine"
                      checked={!replaced}
                      disabled
                      muted={replaced}
                      note={
                        replaced
                          ? t("multiEdit.dialog.replacedByTheirs", {
                              name: authorName,
                            })
                          : undefined
                      }
                    />
                  );
                })}
              </div>
            )}
          </section>

          <section>
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("multiEdit.dialog.theirChanges", { name: authorName })}
              </h3>
              {theirGroups.length > 0 && (
                <span className="text-xs text-muted-foreground">
                  {t("multiEdit.dialog.selectedCount", {
                    selected: takenGroups.length,
                    total: theirGroups.length,
                  })}
                </span>
              )}
            </div>
            {theirGroups.length === 0 ? (
              <p className="text-mmd text-muted-foreground">
                {t("multiEdit.dialog.noTheirChanges")}
              </p>
            ) : (
              <div className="space-y-2">
                {theirGroups.map((group) => (
                  <ChangeRow
                    key={group.targetKey}
                    group={group}
                    side="theirs"
                    checked={takenFromThem.has(group.targetKey)}
                    note={
                      contested.has(group.targetKey)
                        ? t("multiEdit.dialog.replacesYours")
                        : undefined
                    }
                    onToggle={toggleComponent}
                  />
                ))}
              </div>
            )}
          </section>
        </div>

        <ConflictDialogFooter
          summary={footer}
          ownChangeCount={keptOfMine.length}
          confirmingDiscard={confirmingDiscard}
          setConfirmingDiscard={setConfirmingDiscard}
          isPending={isPending}
          isForking={isForking}
          isOverwriting={isOverwriting}
          isDiscarding={isDiscarding}
          onCancel={closeDialog}
          onDiscard={() => void onDiscard()}
          onDuplicate={onDuplicate}
          onOverwrite={onOverwrite}
        />
      </DialogContent>
    </Dialog>
  );
}

export default DuplicateFlowModal;
