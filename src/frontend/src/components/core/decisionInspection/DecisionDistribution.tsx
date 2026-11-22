import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { DecisionEvidence } from "./decision-evidence";
import type { DecisionFormatters } from "./decision-outcome";

interface DecisionDistributionProps {
  evidence: DecisionEvidence;
  format: DecisionFormatters;
}

function ProbabilityCell({
  value,
  format,
}: {
  value: number | undefined;
  format: DecisionFormatters;
}) {
  const { t } = useTranslation();
  if (value === undefined) {
    return (
      <span className="text-muted-foreground">{t("decision.notReported")}</span>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-muted"
        aria-hidden="true"
      >
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${value * 100}%` }}
        />
      </div>
      <span className="tabular-nums">{format.percent(value)}</span>
    </div>
  );
}

/**
 * Every option or level the model evaluated, in the order it was asked, with
 * the probability it reported and the minimum the policy applied to each.
 */
export function DecisionDistribution({
  evidence,
  format,
}: DecisionDistributionProps) {
  const { t } = useTranslation();
  const { candidates, policy, kind } = evidence;
  if (candidates.length === 0) return null;
  const isScore = kind === "score";
  // Score rounds to a level, so it applies no minimum probability.
  const showMinimum = policy !== null && !isScore;
  return (
    <Table data-testid="decision-distribution">
      <caption className="sr-only">
        {t(isScore ? "decision.levelsCaption" : "decision.optionsCaption")}
      </caption>
      <TableHeader>
        <TableRow>
          <TableHead>
            {t(isScore ? "decision.level" : "decision.option")}
          </TableHead>
          <TableHead>{t("decision.probability")}</TableHead>
          {showMinimum && <TableHead>{t("decision.minimum")}</TableHead>}
          <TableHead>
            <span className="sr-only">{t("decision.markers")}</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {candidates.map((candidate, index) => {
          const threshold = policy?.thresholds[candidate.id];
          const activated = policy?.activatedBranch === candidate.id;
          const picked = evidence.selectedOption === candidate.id;
          return (
            <TableRow
              key={candidate.id}
              data-testid={`decision-row-${candidate.id}`}
            >
              <TableCell className="font-medium">
                {isScore && (
                  <span className="mr-1.5 text-muted-foreground tabular-nums">
                    {index}
                  </span>
                )}
                {candidate.label}
              </TableCell>
              <TableCell>
                <ProbabilityCell
                  value={evidence.probabilities?.[candidate.id]}
                  format={format}
                />
              </TableCell>
              {showMinimum && (
                <TableCell className="tabular-nums">
                  {threshold === undefined
                    ? t("decision.notReported")
                    : format.percent(threshold)}
                </TableCell>
              )}
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  {activated && (
                    <Badge variant="successStatic" size="xq">
                      {t("decision.activated")}
                    </Badge>
                  )}
                  {picked && (
                    <Badge variant="secondaryStatic" size="xq">
                      {t("decision.providerPick")}
                    </Badge>
                  )}
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

export default DecisionDistribution;
