import { useState } from "react";
import { useTranslation } from "react-i18next";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { useFlowNames } from "@/hooks/use-history-changes";
import AuthorAvatar from "@/pages/FlowPage/components/flowSidebarComponent/components/FlowVersionSidebar/components/AuthorAvatar";
import { formatTimestamp } from "@/pages/FlowPage/components/flowSidebarComponent/components/FlowVersionSidebar/utils";
import useRevisionPlaybackStore from "@/stores/revisionPlaybackStore";
import { authorColor } from "@/utils/author-color";
import { groupByActor, type NodeChange } from "@/utils/flow-operations/changes";
import { describeOperation } from "@/utils/flow-operations/describe";
import { entryContaining } from "@/utils/flow-operations/history";

interface NodeHistoryChangeProps {
  change: NodeChange;
  /** The node's template, for its fields' display names. */
  template?: Record<string, { display_name?: string } | undefined>;
}

/**
 * Who changed a node at the previewed point in history, as a label above
 * it, and what each of them changed, with when, while the node is hovered.
 *
 * The preview canvas turns pointer events off on its nodes, so a layer over
 * the node takes the hover. It also keeps the node's own controls out of
 * reach, as they are everywhere else in the read-only preview.
 */
export default function NodeHistoryChange({
  change,
  template,
}: NodeHistoryChangeProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const hover = {
    onMouseEnter: () => setOpen(true),
    onMouseLeave: () => setOpen(false),
  };
  const entries = useRevisionPlaybackStore((s) => s.timeline?.entries);
  const names = useFlowNames();
  const nameOf = (username: string | null) =>
    username ?? t("flowHistory.unknownAuthor");
  const fieldLabel = (_nodeId: string, field: string) =>
    template?.[field]?.display_name || undefined;

  const details = (
    <div
      className="flex flex-col gap-2 py-1"
      data-testid="node-history-change-details"
    >
      {groupByActor(change.operations).map((group) => {
        const last = group.operations[group.operations.length - 1];
        const when = entries
          ? entryContaining(entries, last.revision)?.created_at
          : null;
        const sentences = [
          ...new Set(
            group.operations.flatMap((operation) =>
              describeOperation(operation, t, { fieldLabel, names }),
            ),
          ),
        ];
        return (
          <div key={last.revision} className="flex gap-2">
            <AuthorAvatar
              id={group.actor.id}
              name={group.actor.username}
              className="h-5 w-5 text-[10px] ring-0"
            />
            <div className="flex min-w-0 flex-col gap-0.5">
              <div className="flex items-baseline gap-2">
                <span className="font-semibold">
                  {nameOf(group.actor.username)}
                </span>
                {when && (
                  <span className="tabular-nums opacity-70">
                    {formatTimestamp(when)}
                  </span>
                )}
              </div>
              {sentences.map((sentence) => (
                <span key={sentence}>{sentence}</span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <>
      <div
        aria-hidden
        data-testid="node-history-change-hover"
        className="pointer-events-auto absolute inset-0 z-20 rounded-xl"
        {...hover}
      />
      <ShadTooltip content={details} open={open} side="top" align="start">
        <div
          data-testid="node-history-change"
          {...hover}
          className="pointer-events-auto absolute -top-8 left-2 z-20 flex max-w-[calc(100%-1rem)] items-center gap-1.5 rounded-full border-2 bg-background py-0.5 pl-0.5 pr-2 text-xs font-medium text-foreground shadow-sm"
          style={{ borderColor: authorColor(change.actor.id) }}
        >
          <AuthorAvatar
            id={change.actor.id}
            name={change.actor.username}
            className="h-4 w-4 text-[9px] ring-0"
          />
          <span className="truncate">{nameOf(change.actor.username)}</span>
        </div>
      </ShadTooltip>
    </>
  );
}
