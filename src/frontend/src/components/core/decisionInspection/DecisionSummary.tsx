import { useTranslation } from "react-i18next";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { DecisionOutcome, DecisionTone } from "./decision-outcome";

const TONE_VARIANT: Record<DecisionTone, BadgeProps["variant"]> = {
  answered: "successStatic",
  accepted: "successStatic",
  uncertain: "conflictContested",
  refused: "purpleStatic",
  error: "errorStatic",
};

function BranchText({ outcome }: { outcome: DecisionOutcome }) {
  const { t } = useTranslation();
  const branch = outcome.branch;
  if (branch === null) return null;
  const value =
    branch.kind === "route"
      ? branch.label
      : branch.kind === "else"
        ? t("decision.branch.else")
        : t("decision.branch.stopped");
  return (
    <p className="text-sm" data-testid="decision-branch">
      <span className="text-muted-foreground">
        {t("decision.branch.label")}
      </span>{" "}
      <span className="font-medium">{value}</span>
    </p>
  );
}

/** The outcome at a glance: its tone, where the message went, and why. */
export function DecisionSummary({ outcome }: { outcome: DecisionOutcome }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant={TONE_VARIANT[outcome.tone]}
          size="sq"
          data-testid="decision-tone"
        >
          {t(`decision.tone.${outcome.tone}`)}
        </Badge>
        <BranchText outcome={outcome} />
      </div>
      <p className="text-sm text-foreground" data-testid="decision-reason">
        {t(outcome.reasonKey, outcome.reasonParams)}
      </p>
    </div>
  );
}

export default DecisionSummary;
