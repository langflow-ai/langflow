import { useTranslation } from "react-i18next";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SafetyCheck } from "@/controllers/API/queries/evals/types";
import { cn } from "@/utils/utils";
import type { ComparisonEntry } from "../utils/comparison";
import { formatPercent } from "../utils/format";
import VariantLabel from "./VariantLabel";

type Metric = (entry: ComparisonEntry) => number | null;

/** The best value of a column, only when one version alone has it: a shared best marks nothing. */
function bestOf(entries: ComparisonEntry[], metric: Metric, higher: boolean) {
  const values = entries
    .map(metric)
    .filter((value): value is number => value !== null);
  if (values.length < 2) return null;
  const best = higher ? Math.max(...values) : Math.min(...values);
  return values.filter((value) => value === best).length === 1 ? best : null;
}

function resistedRate(entry: ComparisonEntry): number | null {
  const attacks = entry.safety?.attacks;
  return attacks && attacks.total > 0 ? attacks.resisted / attacks.total : null;
}

/** The judge's safety checks per version: share of safe answers, each check's flag rate, attacks resisted. */
export default function ComparisonSafety({
  entries,
}: {
  entries: ComparisonEntry[];
}) {
  const { t } = useTranslation();
  const judged = entries.filter((entry) => entry.safety);
  if (judged.length === 0) return null;
  const checks: SafetyCheck[] = [
    ...new Set(judged.flatMap((entry) => entry.safety?.checks ?? [])),
  ];
  const withAttacks = judged.some((entry) => resistedRate(entry) !== null);
  const safest = bestOf(judged, (entry) => entry.safety?.safe ?? null, true);
  const fewestFlags = Object.fromEntries(
    checks.map((check) => [
      check,
      bestOf(judged, (entry) => entry.safety?.rates[check] ?? null, false),
    ]),
  );
  const mostResisted = bestOf(judged, resistedRate, true);
  const cell = (value: number | null, best: number | null) => (
    <TableCell
      className={cn(
        "text-right tabular-nums",
        best !== null && value === best && "font-semibold",
      )}
    >
      {formatPercent(value)}
    </TableCell>
  );

  return (
    <section
      aria-labelledby="comparison-safety-heading"
      className="flex flex-col gap-2"
      data-testid="comparison-safety"
    >
      <h3 id="comparison-safety-heading" className="text-sm font-medium">
        {t("evals.compare.safetyTitle")}
      </h3>
      <div className="overflow-x-auto rounded-lg border">
        <Table aria-labelledby="comparison-safety-heading">
          <TableHeader>
            <TableRow>
              <TableHead>{t("evals.compare.models")}</TableHead>
              <TableHead className="text-right">
                {t("evals.safety.safe")}
              </TableHead>
              {checks.map((check) => (
                <TableHead key={check} className="text-right">
                  {t(`evals.safety.check.${check}`)}
                </TableHead>
              ))}
              {withAttacks && (
                <TableHead className="text-right">
                  {t("evals.compare.attacksResisted")}
                </TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {judged.map((entry) => (
              <TableRow key={entry.index} data-testid="comparison-safety-row">
                <TableCell className="max-w-72">
                  <VariantLabel
                    index={entry.index}
                    overrides={entry.overrides}
                    detail={false}
                  />
                </TableCell>
                {cell(entry.safety?.safe ?? null, safest)}
                {checks.map((check) => (
                  <TableCell
                    key={check}
                    className={cn(
                      "text-right tabular-nums",
                      fewestFlags[check] !== null &&
                        entry.safety?.rates[check] === fewestFlags[check] &&
                        "font-semibold",
                      Boolean(entry.safety?.rates[check]) && "text-destructive",
                    )}
                  >
                    {formatPercent(entry.safety?.rates[check])}
                  </TableCell>
                ))}
                {withAttacks && (
                  <TableCell
                    className={cn(
                      "text-right tabular-nums",
                      mostResisted !== null &&
                        resistedRate(entry) === mostResisted &&
                        "font-semibold",
                    )}
                  >
                    {entry.safety && entry.safety.attacks.total > 0
                      ? t("evals.compare.ratio", {
                          part: entry.safety.attacks.resisted,
                          total: entry.safety.attacks.total,
                        })
                      : "—"}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">
        {t("evals.compare.safetyLegend")}
      </p>
    </section>
  );
}
