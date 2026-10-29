import { useTranslation } from "react-i18next";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  SAFETY_CHECKS,
  type SafetyCheck,
} from "@/controllers/API/queries/evals/types";

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

  return (
    <fieldset
      className="flex flex-col gap-2"
      aria-describedby="judge-safety-hint"
    >
      <legend className="pb-1 text-sm font-medium">
        {t("evals.safety.title")}
      </legend>
      <p id="judge-safety-hint" className="text-xs text-muted-foreground">
        {t("evals.safety.hint")}
      </p>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {SAFETY_CHECKS.map((check) => {
          const id = `judge-safety-${check}`;
          return (
            <div key={check} className="flex items-start gap-2">
              <Checkbox
                id={id}
                data-testid={id}
                checked={value.includes(check)}
                onCheckedChange={(checked) => setCheck(check, checked === true)}
                aria-describedby={`${id}-hint`}
                className="mt-0.5"
              />
              <div className="flex flex-col gap-0.5">
                <Label htmlFor={id} className="font-normal">
                  {t(`evals.safety.check.${check}`)}
                </Label>
                <span
                  id={`${id}-hint`}
                  className="text-xs text-muted-foreground"
                >
                  {t(`evals.safety.checkHint.${check}`)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}
