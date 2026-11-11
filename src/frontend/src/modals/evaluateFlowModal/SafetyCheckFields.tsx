import { useTranslation } from "react-i18next";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  SAFETY_CHECKS,
  type SafetyCheck,
} from "@/controllers/API/queries/evals/types";
import InfoHint from "@/pages/MainPage/pages/evalsPage/components/InfoHint";
import CollapsibleSection from "./CollapsibleSection";

interface SafetyCheckFieldsProps {
  value: readonly SafetyCheck[];
  onChange: (value: SafetyCheck[]) => void;
}

/** What the judge also checks on each answer; any flagged check fails the row. */
export default function SafetyCheckFields({
  value,
  onChange,
}: SafetyCheckFieldsProps) {
  const { t } = useTranslation();
  const setCheck = (check: SafetyCheck, on: boolean) =>
    onChange(
      SAFETY_CHECKS.filter((item) =>
        item === check ? on : value.includes(item),
      ),
    );
  const summary =
    value.length > 0
      ? value.map((check) => t(`evals.safety.check.${check}`)).join(", ")
      : t("evals.safety.none");

  return (
    <CollapsibleSection
      id="judge-safety"
      title={t("evals.safety.title")}
      summary={summary}
    >
      <fieldset
        className="flex min-w-0 flex-col gap-2"
        aria-describedby="judge-safety-hint"
      >
        <legend className="sr-only">{t("evals.safety.title")}</legend>
        <p id="judge-safety-hint" className="text-xs text-muted-foreground">
          {t("evals.safety.hint")}
        </p>
        <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
          {SAFETY_CHECKS.map((check) => {
            const id = `judge-safety-${check}`;
            const label = t(`evals.safety.check.${check}`);
            return (
              <div key={check} className="flex items-center gap-2">
                <Checkbox
                  id={id}
                  data-testid={id}
                  checked={value.includes(check)}
                  onCheckedChange={(checked) =>
                    setCheck(check, checked === true)
                  }
                />
                <Label htmlFor={id} className="font-normal">
                  {label}
                </Label>
                <InfoHint
                  hint={t(`evals.safety.checkHint.${check}`)}
                  label={t("evals.infoLabel", { name: label })}
                  testId={`${id}-info`}
                />
              </div>
            );
          })}
        </div>
      </fieldset>
    </CollapsibleSection>
  );
}
