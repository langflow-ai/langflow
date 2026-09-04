import { useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetFlowVersionDiff } from "@/controllers/API/queries/flow-version";
import type {
  FlowVersionDiffCodeChange,
  FlowVersionDiffEdgeRef,
  FlowVersionDiffFieldChange,
  FlowVersionDiffNodeChange,
  FlowVersionDiffNodeRef,
} from "@/types/flow/version";
import { cn } from "@/utils/utils";
import { COMPARE_DRAFT_TARGET } from "../constants";
import {
  buildSummaryChips,
  describeDiffSide,
  formatDiffValue,
  parseUnifiedDiffLines,
} from "../diff-utils";

interface CompareVersionsDialogProps {
  flowId: string;
  /** The version the comparison starts from. */
  baseVersionId: string;
  /** A version id, or the draft sentinel, to compare against. */
  against: string;
  onClose: () => void;
  onSwap: () => void;
}

/**
 * The removed side needs a per-theme red: `destructive` clears AA on the light
 * surface but only reaches 3.9:1 on the dark one, and `accent-red-foreground`
 * is the reverse. The added side needs none — `accent-emerald-foreground` is
 * already authored per theme for this.
 */
const REMOVED_TEXT = "text-destructive dark:text-accent-red-foreground";

const TONE_CLASSES: Record<string, string> = {
  added: "bg-accent-emerald text-accent-emerald-foreground",
  removed: `bg-destructive/10 ${REMOVED_TEXT}`,
  modified: "bg-accent-amber text-accent-amber-foreground",
  secret: "bg-muted text-muted-foreground",
};

function NodeRefRow({ node }: { node: FlowVersionDiffNodeRef }) {
  return (
    <li className="flex items-baseline gap-2 py-1">
      <span className="font-medium text-sm">
        {node.display_name || node.id}
      </span>
      {node.component_type && (
        <span className="text-xs text-muted-foreground">
          {node.component_type}
        </span>
      )}
    </li>
  );
}

function EdgeRefRow({ edge }: { edge: FlowVersionDiffEdgeRef }) {
  const source = edge.source_handle_name
    ? `${edge.source} · ${edge.source_handle_name}`
    : edge.source;
  const target = edge.target_handle_name
    ? `${edge.target} · ${edge.target_handle_name}`
    : edge.target;
  return (
    <li className="py-1 font-mono text-xs text-muted-foreground">
      {source} → {target}
    </li>
  );
}

function FieldChangeRow({ change }: { change: FlowVersionDiffFieldChange }) {
  const { t } = useTranslation();
  return (
    <tr className="border-t align-top">
      <td className="py-1.5 pr-3 font-medium text-xs">
        {change.display_name || change.name}
      </td>
      {change.redacted ? (
        <td colSpan={2} className="py-1.5">
          <span
            data-testid="redacted-value-pill"
            className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
          >
            <ForwardedIconComponent name="EyeOff" className="h-3 w-3" />
            {t("flowVersion.valueHidden")}
          </span>
        </td>
      ) : (
        <>
          <td className="py-1.5 pr-3">
            <pre
              className={cn(
                "whitespace-pre-wrap break-all font-mono text-xs",
                REMOVED_TEXT,
              )}
            >
              {formatDiffValue(change.before)}
            </pre>
          </td>
          <td className="py-1.5">
            <pre className="whitespace-pre-wrap break-all font-mono text-xs text-accent-emerald-foreground">
              {formatDiffValue(change.after)}
            </pre>
          </td>
        </>
      )}
    </tr>
  );
}

function CodeChangeBlock({ change }: { change: FlowVersionDiffCodeChange }) {
  const { t } = useTranslation();
  const lines = parseUnifiedDiffLines(change.unified_diff);
  return (
    <div className="mt-2 rounded-md border">
      <div className="flex items-center gap-2 border-b px-2 py-1">
        <span className="font-medium text-xs">
          {change.display_name || change.field_name}
        </span>
        <span className="text-xs text-accent-emerald-foreground">
          +{change.added_lines}
        </span>
        <span className={cn("text-xs", REMOVED_TEXT)}>
          -{change.removed_lines}
        </span>
        {change.redacted && (
          <span className="text-xs text-muted-foreground">
            {t("flowVersion.valueHidden")}
          </span>
        )}
        {change.truncated && (
          <span className="text-xs text-muted-foreground">
            {t("flowVersion.codeDiffTruncated")}
          </span>
        )}
      </div>
      {lines.length > 0 && (
        <pre className="max-h-64 overflow-auto p-2 font-mono text-xs leading-5">
          {lines.map((line, index) => (
            <div
              // Diff lines are positional and repeat verbatim, so the index is
              // the only stable identity available here.
              key={`${index}-${line.text}`}
              className={cn(
                line.kind === "add" &&
                  "bg-accent-emerald text-accent-emerald-foreground",
                line.kind === "del" && `bg-destructive/10 ${REMOVED_TEXT}`,
                line.kind === "meta" && "text-muted-foreground",
              )}
            >
              {line.text || " "}
            </div>
          ))}
        </pre>
      )}
    </div>
  );
}

function ModifiedNodeBlock({ node }: { node: FlowVersionDiffNodeChange }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(true);
  const hasDetail =
    node.field_changes.length > 0 ||
    node.code_changes.length > 0 ||
    !!node.display_name_change;

  return (
    <div className="border-b py-2 last:border-b-0">
      <button
        type="button"
        onClick={() => setExpanded((open) => !open)}
        className="flex w-full items-center gap-2 text-left"
      >
        <ForwardedIconComponent
          name={expanded ? "ChevronDown" : "ChevronRight"}
          className="h-3.5 w-3.5 text-muted-foreground"
        />
        <span className="font-medium text-sm">
          {node.display_name || node.id}
        </span>
        {node.component_type && (
          <span className="text-xs text-muted-foreground">
            {node.component_type}
          </span>
        )}
      </button>

      {expanded && (
        <div className="pl-5 pt-1">
          {node.display_name_change && (
            <p className="py-1 text-xs text-muted-foreground">
              {node.display_name_change.before} →{" "}
              {node.display_name_change.after}
            </p>
          )}
          {node.field_changes.length > 0 && (
            <table className="w-full table-fixed">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="w-1/4 pb-1 font-normal">
                    {t("flowVersion.fieldColumn")}
                  </th>
                  <th className="w-3/8 pb-1 font-normal">
                    {t("flowVersion.beforeColumn")}
                  </th>
                  <th className="w-3/8 pb-1 font-normal">
                    {t("flowVersion.afterColumn")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {node.field_changes.map((change) => (
                  <FieldChangeRow key={change.name} change={change} />
                ))}
              </tbody>
            </table>
          )}
          {node.code_changes.map((change) => (
            <CodeChangeBlock key={change.field_name} change={change} />
          ))}
          {node.other_changed_keys.length > 0 && (
            <p className="pt-1 font-mono text-xs text-muted-foreground">
              {node.other_changed_keys.join(", ")}
            </p>
          )}
          {!hasDetail && node.other_changed_keys.length === 0 && (
            <p className="text-xs text-muted-foreground">
              {t("flowVersion.noDifferences")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  if (count === 0) return null;
  return (
    <section className="py-2">
      <h3 className="pb-1 font-semibold text-sm">
        {title} ({count})
      </h3>
      {children}
    </section>
  );
}

export default function CompareVersionsDialog({
  flowId,
  baseVersionId,
  against,
  onClose,
  onSwap,
}: CompareVersionsDialogProps) {
  const { t } = useTranslation();
  const {
    data: diff,
    isLoading,
    isError,
  } = useGetFlowVersionDiff({ flowId, versionId: baseVersionId, against });

  const canSwap = against !== COMPARE_DRAFT_TARGET;
  const draftLabel = t("flowVersion.currentDraft");
  const baseLabel = describeDiffSide(diff?.base, draftLabel);
  const targetLabel = describeDiffSide(diff?.target, draftLabel);
  const chips = buildSummaryChips(diff?.summary);

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="mx-4 flex max-h-[80vh] w-full max-w-4xl flex-col rounded-xl border bg-background shadow-lg">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-2">
            <ForwardedIconComponent name="GitCompare" className="h-4 w-4" />
            <span className="font-semibold text-sm">
              {baseLabel && targetLabel
                ? t("flowVersion.compareTitle", {
                    base: baseLabel,
                    target: targetLabel,
                  })
                : t("flowVersion.compareWith")}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="iconMd"
              onClick={onSwap}
              // The draft has no version id and the endpoint takes the base as a
              // path parameter, so it can only ever be the right-hand side.
              disabled={!canSwap}
              title={
                canSwap
                  ? t("flowVersion.compareSwap")
                  : t("flowVersion.compareSwapUnavailable")
              }
              aria-label={t("flowVersion.compareSwap")}
            >
              <ForwardedIconComponent
                name="ArrowLeftRight"
                className="h-4 w-4"
              />
            </Button>
            <Button
              variant="ghost"
              size="iconMd"
              onClick={onClose}
              aria-label={t("deleteModal.cancel")}
            >
              <ForwardedIconComponent name="X" className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {chips.length > 0 && (
          <div className="flex flex-wrap gap-2 border-b px-4 py-2">
            {chips.map((chip) => (
              <span
                key={chip.key}
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs",
                  TONE_CLASSES[chip.tone],
                )}
              >
                {t(`flowVersion.summary.${chip.key}`, { count: chip.count })}
              </span>
            ))}
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-4 py-2">
          {isLoading && (
            <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground text-sm">
              <ForwardedIconComponent
                name="Loader2"
                className="h-4 w-4 animate-spin"
              />
              {t("flowVersion.compareLoading")}
            </div>
          )}

          {isError && (
            <div className="bg-destructive/10 px-2 py-2 text-destructive text-xs">
              {t("flowVersion.failedToLoadDiff")}
            </div>
          )}

          {diff && diff.identical && (
            <p className="py-8 text-center text-muted-foreground text-sm">
              {t("flowVersion.noDifferences")}
            </p>
          )}

          {diff && !diff.identical && (
            <>
              {diff.truncated && (
                <p className="py-1 text-muted-foreground text-xs">
                  {t("flowVersion.diffTruncated")}
                </p>
              )}
              <Section
                title={t("flowVersion.nodesAddedTitle")}
                count={diff.nodes.added.length}
              >
                <ul>
                  {diff.nodes.added.map((node) => (
                    <NodeRefRow key={node.id} node={node} />
                  ))}
                </ul>
              </Section>
              <Section
                title={t("flowVersion.nodesRemovedTitle")}
                count={diff.nodes.removed.length}
              >
                <ul>
                  {diff.nodes.removed.map((node) => (
                    <NodeRefRow key={node.id} node={node} />
                  ))}
                </ul>
              </Section>
              <Section
                title={t("flowVersion.nodesModifiedTitle")}
                count={diff.nodes.modified.length}
              >
                <div>
                  {diff.nodes.modified.map((node) => (
                    <ModifiedNodeBlock key={node.id} node={node} />
                  ))}
                </div>
              </Section>
              <Section
                title={t("flowVersion.edgesAddedTitle")}
                count={diff.edges.added.length}
              >
                <ul>
                  {diff.edges.added.map((edge) => (
                    <EdgeRefRow key={edge.id} edge={edge} />
                  ))}
                </ul>
              </Section>
              <Section
                title={t("flowVersion.edgesRemovedTitle")}
                count={diff.edges.removed.length}
              >
                <ul>
                  {diff.edges.removed.map((edge) => (
                    <EdgeRefRow key={edge.id} edge={edge} />
                  ))}
                </ul>
              </Section>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
