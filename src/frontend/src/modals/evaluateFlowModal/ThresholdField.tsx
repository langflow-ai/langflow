import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** The weighted score a row needs to pass. */
export default function ThresholdField({
  value,
  onChange,
}: {
  value: number;
  onChange: (value: number) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Label htmlFor="evaluation-threshold" className="shrink-0">
        {t("evals.evaluate.threshold")}
      </Label>
      <div className="w-24 shrink-0">
        <Input
          id="evaluation-threshold"
          type="number"
          min={0}
          max={1}
          step={0.05}
          className="h-9 w-full"
          value={value}
          aria-describedby="evaluation-threshold-hint"
          onChange={(event) => {
            const next = Number(event.target.value);
            if (!Number.isNaN(next)) onChange(Math.min(1, Math.max(0, next)));
          }}
        />
      </div>
      <span
        id="evaluation-threshold-hint"
        className="text-xs text-muted-foreground"
      >
        {t("evals.evaluate.thresholdHint")}
      </span>
    </div>
  );
}
