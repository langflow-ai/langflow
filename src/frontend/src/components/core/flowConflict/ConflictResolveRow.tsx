import * as AccordionPrimitive from "@radix-ui/react-accordion";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { ChangeGroup } from "@/utils/flow-diff";
import { cn } from "@/utils/utils";
import { RawDiff } from "./ChangeRow";

/** The single item id: this accordion holds one card, opened or closed. */
const OPEN = "versions";

/** Which version of a contested component wins, or nothing chosen yet. */
export type ConflictChoice = "mine" | "theirs" | null;

type ConflictResolveRowProps = {
  /** The same component as both people left it. */
  mine: ChangeGroup;
  theirs: ChangeGroup;
  authorName: string;
  choice: ConflictChoice;
  onChoose: (targetKey: string, side: "mine" | "theirs") => void;
};

/** The one line of each side, so the choice reads as a comparison. */
function summarise(group: ChangeGroup, t: (k: string, p?: object) => string) {
  return group.changes
    .map((change) =>
      // Values are dropped here even when they are short enough to inline.
      // Two of these sit one above the other, and a pair of long quotations is
      // read as prose rather than compared; the raw diff is where the values
      // are meant to be weighed.
      change.sentence.key === "multiEdit.change.fieldShort"
        ? t("multiEdit.change.fieldLong", {
            field: change.sentence.params.field,
          })
        : t(change.sentence.key, change.sentence.params),
    )
    .join(" ");
}

/** One side of the choice, with the raw before/after behind a control. */
function VersionOption({
  side,
  label,
  group,
  radioId,
  selected,
  divider,
}: {
  side: "mine" | "theirs";
  label: string;
  group: ChangeGroup;
  radioId: string;
  selected: boolean;
  divider: boolean;
}) {
  const { t } = useTranslation();
  const [showDiff, setShowDiff] = useState(false);
  const detailed = group.changes.filter((change) => change.detail);

  return (
    <div
      className={cn(
        "px-3 py-2.5",
        divider && "border-b border-muted",
        // The standing answer is lifted off the card, the way the design
        // separates the choice already made from the one still offered.
        selected && "bg-muted/60",
      )}
    >
      <label
        htmlFor={radioId}
        className="flex cursor-pointer items-start gap-3"
      >
        <RadioGroupItem id={radioId} value={side} className="mt-0.5" />
        <span className="flex min-w-0 flex-col">
          <span className="text-[13px] font-medium leading-[19.5px] text-secondary-foreground">
            {label}
          </span>
          <span className="text-[12px] font-medium leading-[19.5px] text-muted-foreground">
            {summarise(group, t)}
          </span>
        </span>
      </label>
      {detailed.length > 0 && (
        <div className="pl-[27px]">
          <button
            type="button"
            onClick={() => setShowDiff((open) => !open)}
            aria-expanded={showDiff}
            className="flex items-center gap-1 text-[12px] font-medium leading-[19.5px] text-muted-foreground underline-offset-2 hover:underline"
          >
            <ForwardedIconComponent
              name={showDiff ? "ChevronDown" : "ChevronRight"}
              className="h-3 w-3"
              aria-hidden="true"
            />
            {showDiff
              ? t("multiEdit.dialog.hideChanges")
              : t("multiEdit.dialog.showChanges")}
          </button>
          {showDiff &&
            detailed.map((change) => (
              <RawDiff
                key={change.id}
                before={change.detail?.before ?? ""}
                after={change.detail?.after ?? ""}
              />
            ))}
        </div>
      )}
    </div>
  );
}

/**
 * A component both people edited, and the choice between their two versions.
 *
 * Collapsed until asked for: a conflict is a decision, not a diff to read, and
 * a dialog that opens with every comparison unfolded buries the one thing the
 * reader has to do. The header carries the verdict either way — what is still
 * outstanding, or what was chosen.
 *
 * Nothing is preselected. A default here would be a decision made on the
 * reader's behalf and then presented as theirs, which is the exact failure the
 * whole conflict flow exists to prevent.
 */
export function ConflictResolveRow({
  mine,
  theirs,
  authorName,
  choice,
  onChoose,
}: ConflictResolveRowProps) {
  const { t } = useTranslation();
  const name = useId();
  const resolved = choice !== null;
  const [expanded, setExpanded] = useState(false);

  const choose = (value: string) => {
    onChoose(theirs.targetKey, value as "mine" | "theirs");
    // Folded away once answered: the summary line now says everything the open
    // card did, and the next unresolved conflict moves into view.
    setExpanded(false);
  };

  return (
    <AccordionPrimitive.Root
      type="single"
      collapsible
      value={expanded ? OPEN : ""}
      onValueChange={(value) => setExpanded(value === OPEN)}
      className={cn(
        "overflow-hidden rounded-[10px] border",
        resolved
          ? "border-muted bg-muted/40"
          : "border-conflict-outline bg-transparent",
      )}
      data-testid={`conflict-resolve-${theirs.targetKey}`}
    >
      <AccordionPrimitive.Item value={OPEN} className="border-none">
        <AccordionPrimitive.Header className="flex items-start gap-3 px-3 py-2.5">
          {resolved ? (
            <Checkbox
              checked
              disabled
              aria-label={t("multiEdit.dialog.resolvedLabel", {
                component: theirs.label,
              })}
              className="mt-0.5"
            />
          ) : (
            <div
              className="mt-0.5 flex size-[22px] shrink-0 items-center justify-center rounded-md border border-accent-amber-foreground/40 bg-accent-amber-foreground/10"
              aria-hidden="true"
            >
              <ForwardedIconComponent
                name="TriangleAlert"
                className="h-3.5 w-3.5 text-accent-amber-foreground"
              />
            </div>
          )}
          <div className="min-w-0 flex-1">
            {/* The name and its sentence share this column; the badge sits on
                the right edge with the chevron, lined up with every other. */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[13px] font-semibold leading-[19.5px] text-foreground">
                {theirs.label}
              </span>
              <span className="text-[13px] leading-[19.5px] text-muted-foreground">
                {t("multiEdit.dialog.conflictDescription")}
              </span>
            </div>
            {resolved ? (
              <p className="flex items-center gap-1.5 pt-0.5 text-[12px] font-medium leading-[19.5px] text-muted-foreground">
                <ForwardedIconComponent
                  name="Check"
                  className="h-3 w-3 shrink-0 text-accent-emerald-foreground"
                  aria-hidden="true"
                />
                {choice === "mine"
                  ? t("multiEdit.dialog.keepingMine")
                  : t("multiEdit.dialog.keepingTheirs", { name: authorName })}
              </p>
            ) : (
              <p className="pt-0.5 text-[12px] font-medium leading-[19.5px] text-muted-foreground">
                {t("multiEdit.dialog.chooseVersion")}
              </p>
            )}
          </div>
          {!resolved && (
            <Badge
              variant="conflictContested"
              size="change"
              className="mt-0.5 shrink-0"
            >
              {t("multiEdit.badge.actionRequired")}
            </Badge>
          )}
          <AccordionPrimitive.Trigger asChild>
            <button
              type="button"
              aria-label={t(
                expanded
                  ? "multiEdit.dialog.collapseConflict"
                  : "multiEdit.dialog.expandConflict",
                { component: theirs.label },
              )}
              className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground [&[data-state=open]>svg]:rotate-180"
              data-testid={`conflict-toggle-${theirs.targetKey}`}
            >
              <ForwardedIconComponent
                name="ChevronDown"
                className="h-4 w-4 transition-transform duration-200 motion-reduce:transition-none"
                aria-hidden="true"
              />
            </button>
          </AccordionPrimitive.Trigger>
        </AccordionPrimitive.Header>
        {/* The height Radix measures is what the keyframes animate between, so
            the card grows into its content instead of appearing at full size. */}
        <AccordionPrimitive.Content className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down motion-reduce:animate-none">
          <div className="border-t border-muted">
            <RadioGroup
              value={choice ?? ""}
              onValueChange={choose}
              className="gap-0"
              aria-label={t("multiEdit.dialog.chooseVersionFor", {
                component: theirs.label,
              })}
            >
              <VersionOption
                side="mine"
                label={t("multiEdit.dialog.keepMine")}
                group={mine}
                radioId={`${name}-mine`}
                selected={choice === "mine"}
                divider
              />
              <VersionOption
                side="theirs"
                label={t("multiEdit.dialog.keepTheirs", { name: authorName })}
                group={theirs}
                radioId={`${name}-theirs`}
                selected={choice === "theirs"}
                divider={false}
              />
            </RadioGroup>
          </div>
        </AccordionPrimitive.Content>
      </AccordionPrimitive.Item>
    </AccordionPrimitive.Root>
  );
}

export default ConflictResolveRow;
