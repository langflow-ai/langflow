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
import { usePostForkFlow } from "@/controllers/API/queries/flows/use-post-fork-flow";
import { usePostOverwriteFlow } from "@/controllers/API/queries/flows/use-post-overwrite-flow";
import { adoptServerVersionOnCanvas } from "@/hooks/flows/adopt-version-on-canvas";
import {
  attachTheirFlow,
  refreshConflictState,
} from "@/hooks/flows/conflict-actions";
import { useTakeLatestVersion } from "@/hooks/flows/use-take-latest-version";
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
import { withoutLoadRefreshes } from "@/utils/load-refreshes";
import ChangeRow from "./ChangeRow";
import ConflictDialogFooter from "./ConflictDialogFooter";
import type { ConflictChoice } from "./ConflictResolveRow";
import ConflictResolveRow from "./ConflictResolveRow";

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
  const { takeLatestVersion, isTaking: isLoadingLatest } =
    useTakeLatestVersion();
  const { mutate: forkFlow, isPending: isForking } = usePostForkFlow();
  const { mutate: overwriteFlow, isPending: isOverwriting } =
    usePostOverwriteFlow();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Which contested components have been answered. Separate from `selected`
  // because "not decided yet" and "decided to keep mine" both leave nothing of
  // theirs selected, and only one of them may leave the dialog.
  const [decided, setDecided] = useState<Map<string, "mine" | "theirs">>(
    new Map(),
  );
  // Rebuilding after a refusal is asynchronous, and until it lands the dialog is
  // still describing the version that was just refused. Leaving the actions live
  // through it lets a second click resend the same stale token.
  const [isRebuilding, setIsRebuilding] = useState(false);
  // Discarding cannot be undone, so it is asked twice: the first click states
  // what will be lost, the second does it.
  const isPending =
    isForking || isOverwriting || isRebuilding || isLoadingLatest;
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

  // Keyed on dialogOpen too: the modal stays mounted, so edits made after the refusal must re-enter the diff.
  const { theirChanges, myGroups, theirGroups, contested, theirGraph } =
    useMemo(() => {
      const baseFlow = useFlowsManagerStore.getState().currentFlow;
      const live = useFlowStore.getState();
      const base = baseFlow?.data ?? null;
      const mine = { nodes: live.nodes, edges: live.edges };
      const theirs = conflict?.theirFlow?.data ?? null;
      const flowId = conflict?.flowId;

      // Without the version we loaded there is no way to tell our edits from
      // theirs, so the dialog offers nothing to merge and still duplicates.
      const mineDiff = base
        ? withoutLoadRefreshes(flowId, diffGraphs(base, mine))
        : [];
      const theirsDiff =
        base && theirs
          ? withoutLoadRefreshes(flowId, diffGraphs(base, theirs))
          : [];

      return {
        myChanges: mineDiff,
        theirChanges: theirsDiff,
        // One row per component: it is adopted whole or not at all, so a row per
        // change offered checkboxes that could only ever move together.
        myGroups: groupChangesByTarget(mineDiff),
        theirGroups: groupChangesByTarget(theirsDiff),
        contested: contestedTargetKeys(mineDiff, theirsDiff),
        theirGraph: theirs,
      };
    }, [conflict?.theirFlow, dialogOpen]);

  if (!conflict) return null;

  const authorName = conflict.author.username || t("multiEdit.unknownAuthor");

  // Components whose contested decision currently sits with them. My own changes
  // to those components are shown as replaced rather than quietly dropped.
  const takenFromThem = new Set(
    theirChanges
      .filter((change) => selected.has(change.id))
      .map((change) => change.targetKey),
  );
  // Their changes split by what the choice costs: replacing something of mine,
  // or simply adding to it.
  const conflictGroups = theirGroups.filter((group) =>
    contested.has(group.targetKey),
  );
  const additionalGroups = theirGroups.filter(
    (group) => !contested.has(group.targetKey),
  );
  const mineByKey = new Map(myGroups.map((group) => [group.targetKey, group]));

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

  const chooseSide = (targetKey: string, side: "mine" | "theirs") => {
    setDecided((current) => new Map(current).set(targetKey, side));
    setSelected((current) => {
      const next = new Set(current);
      for (const id of siblingChangeIds(theirChanges, targetKey)) {
        if (side === "theirs") next.add(id);
        else next.delete(id);
      }
      return next;
    });
  };

  // Every contested component has to be answered before the original flow can
  // be written. Left to a default, the dialog would resolve the conflict on the
  // reader's behalf and then save it under their name.
  const unresolved = conflictGroups.filter(
    (group) => !decided.has(group.targetKey),
  ).length;

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
    const live = useFlowStore.getState();
    const merged = applySelectedChanges(
      { nodes: live.nodes, edges: live.edges },
      theirGraph,
      theirChanges,
      selected,
    );
    const viewport = useFlowStore
      .getState()
      .reactFlowInstance?.getViewport() ?? { x: 0, y: 0, zoom: 1 };
    return { ...merged, viewport };
  };

  const onLoadLatest = async () => {
    if (!claimSubmission()) return;
    try {
      await takeLatestVersion(conflict.flowId);
    } finally {
      releaseSubmission();
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
    setDecided(new Map());
    openDialog();
    setErrorData({ title: t("multiEdit.dialog.overwriteMovedAgain") });
  };

  return (
    <Dialog open={dialogOpen} onOpenChange={(open) => !open && closeDialog()}>
      <DialogContent
        hideCloseButton
        overlayClassName="bg-black/60"
        className="w-[560px] max-w-[560px] gap-0 overflow-hidden rounded-[14px] border-muted bg-background p-0 shadow-[0_24px_64px_rgba(0,0,0,0.6)]"
        data-testid="duplicate-flow-modal"
      >
        <DialogHeader className="flex-row items-start justify-between space-y-0 border-b border-muted px-5 py-4 text-left">
          <div className="flex min-w-0 flex-col gap-0.5">
            <DialogTitle className="text-base font-semibold leading-6 text-foreground">
              {t("multiEdit.dialog.title")}
            </DialogTitle>
            <DialogDescription className="text-[13px] leading-[19.5px] text-muted-foreground">
              {t("multiEdit.dialog.subtitle")}
            </DialogDescription>
          </div>
          <button
            type="button"
            onClick={closeDialog}
            aria-label={t("common.close")}
            className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ForwardedIconComponent
              name="X"
              className="h-4 w-4"
              aria-hidden="true"
            />
          </button>
        </DialogHeader>

        {/* Padded on every side the scroll box clips: without the bottom, the last
            row's border sits exactly on the overflow edge and is shaved off. */}
        <div className="max-h-[55vh] space-y-5 overflow-y-auto px-5 py-4">
          <section>
            {myGroups.length === 0 ? (
              <p className="text-[13px] leading-[19.5px] text-muted-foreground">
                {t("multiEdit.dialog.noYourChanges")}
              </p>
            ) : (
              <div className="mb-2.5 flex flex-col gap-0.5">
                <h3 className="text-[11px] uppercase leading-[16.5px] tracking-[0.55px] text-muted-foreground">
                  {t("multiEdit.dialog.yourChanges")}
                </h3>
                <span className="text-xs leading-[18px] text-placeholder">
                  {t("multiEdit.dialog.yourChangesHint")}
                </span>
              </div>
            )}
            {myGroups.length > 0 && (
              <div className="space-y-1.5">
                {/* Contested components lead the list. They are the only rows
                    here that ask for anything, and below the settled ones they
                    were read as part of the same "already included" block. */}
                {conflictGroups.map((group) => {
                  const mine = mineByKey.get(group.targetKey);
                  if (!mine) return null;
                  return (
                    <ConflictResolveRow
                      key={group.targetKey}
                      mine={mine}
                      theirs={group}
                      authorName={authorName}
                      choice={
                        (decided.get(group.targetKey) ?? null) as ConflictChoice
                      }
                      onChoose={chooseSide}
                    />
                  );
                })}
                {myGroups
                  .filter((group) => !contested.has(group.targetKey))
                  .map((group) => (
                    <ChangeRow
                      key={group.targetKey}
                      group={group}
                      side="mine"
                      // The radios above own the contested decisions, so every
                      // row left here is included and says so rather than
                      // offering a choice it cannot honour.
                      checked
                      disabled
                    />
                  ))}
              </div>
            )}
          </section>

          {additionalGroups.length > 0 && (
            <section>
              <div className="mb-2.5 flex flex-col gap-0.5">
                <h3 className="text-[11px] uppercase leading-[16.5px] tracking-[0.55px] text-muted-foreground">
                  {t("multiEdit.dialog.changesAvailable")}
                </h3>
                <span className="text-xs leading-[18px] text-placeholder">
                  {t("multiEdit.dialog.selectChanges")}
                </span>
              </div>
              <div className="space-y-1.5">
                {additionalGroups.map((group) => (
                  <ChangeRow
                    key={group.targetKey}
                    group={group}
                    side="theirs"
                    checked={takenFromThem.has(group.targetKey)}
                    onToggle={toggleComponent}
                  />
                ))}
              </div>
            </section>
          )}

          {theirGroups.length === 0 && (
            <p className="text-[13px] leading-[19.5px] text-muted-foreground">
              {t("multiEdit.dialog.noTheirChanges")}
            </p>
          )}
        </div>

        <ConflictDialogFooter
          isPending={isPending}
          unresolvedConflicts={unresolved}
          isForking={isForking}
          isOverwriting={isOverwriting}
          isLoadingLatest={isLoadingLatest}
          onCancel={closeDialog}
          onLoadLatest={() => void onLoadLatest()}
          onDuplicate={onDuplicate}
          onOverwrite={onOverwrite}
        />
      </DialogContent>
    </Dialog>
  );
}

export default DuplicateFlowModal;
