import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type {
  FlowModelPicker,
  ModelSelection,
} from "@/controllers/API/queries/evals/types";
import { modelKindOfField } from "@/utils/model-kind";
import { cn } from "@/utils/utils";
import ModelOverrideRow from "./ModelOverrideRow";
import { type ChosenModels, pickerKey, sameModel } from "./modelOverrideUtils";

interface ModelOverridesProps {
  flowId: string;
  pickers: readonly FlowModelPicker[];
  chosen: ChosenModels;
  onChange: (key: string, value: ModelSelection | null) => void;
}

/** The flow's model pickers, folded away: a run can try other models without editing the flow. */
export default function ModelOverrides({
  flowId,
  pickers,
  chosen,
  onChange,
}: ModelOverridesProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const rows = pickers.flatMap((picker) => {
    const kind = modelKindOfField({ model_type: picker.model_type });
    return kind ? [{ picker, kind }] : [];
  });
  if (rows.length === 0) return null;
  const changed = rows.filter(({ picker }) => {
    const value = chosen[pickerKey(picker)];
    return value !== undefined && !sameModel(value, picker.value);
  }).length;
  const summary =
    changed > 0
      ? t("evals.evaluate.modelsChanged", { count: changed })
      : t("evals.evaluate.modelsAsInFlow");

  return (
    <div className="flex flex-col gap-4">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 self-start rounded-sm text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        data-testid="evaluate-models"
      >
        <ForwardedIconComponent
          name="ChevronRight"
          aria-hidden="true"
          className={cn(
            "h-4 w-4 transition-transform motion-reduce:transition-none",
            open && "rotate-90",
          )}
        />
        <span className="font-medium">{t("evals.evaluate.models")}</span>
        <span className="text-muted-foreground">{summary}</span>
      </button>
      {/* A display utility outranks the `hidden` attribute, so the closed panel needs the class too. */}
      <div
        id={panelId}
        hidden={!open}
        className={cn("flex flex-col gap-4 border-l pl-4", !open && "hidden")}
      >
        <p className="text-xs text-muted-foreground">
          {t("evals.evaluate.modelsHint")}
        </p>
        {rows.map(({ picker, kind }) => (
          <ModelOverrideRow
            key={pickerKey(picker)}
            flowId={flowId}
            picker={picker}
            kind={kind}
            chosen={chosen[pickerKey(picker)]}
            onChange={(value) => onChange(pickerKey(picker), value)}
          />
        ))}
      </div>
    </div>
  );
}
