import { useTranslation } from "react-i18next";
import type { ScoreEntry } from "@/controllers/API/queries/evals/types";
import { cn } from "@/utils/utils";

/** The judge's safety verdict on one answer: each check that ran, and what the input tried. */
export default function SafetyFlags({ entry }: { entry: ScoreEntry }) {
  const { t } = useTranslation();
  const checks = Object.entries(entry.safety ?? {});
  if (checks.length === 0) return null;
  const attack = entry.input_attack;

  return (
    <div className="flex flex-col gap-1.5 pt-1" data-testid="result-safety">
      <ul
        aria-label={t("evals.safety.title")}
        className="flex flex-wrap gap-1.5"
      >
        {checks.map(([check, failed]) => (
          <li
            key={check}
            className={cn(
              "rounded-md border px-2 py-0.5 text-xs",
              failed
                ? "border-destructive/50 text-destructive"
                : "text-muted-foreground",
            )}
          >
            {t(`evals.safety.check.${check}`)}:{" "}
            {failed ? t("evals.safety.flagged") : t("evals.safety.clear")}
          </li>
        ))}
      </ul>
      {attack && attack !== "none" && (
        <span className="text-xs text-muted-foreground">
          {t("evals.safety.inputAttack", {
            attack: t(`evals.safety.attack.${attack}`),
          })}
        </span>
      )}
    </div>
  );
}
