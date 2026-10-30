import { useTranslation } from "react-i18next";
import ModelInputComponent from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type {
  FlowModelPicker,
  ModelSelection,
} from "@/controllers/API/queries/evals/types";
import type { ModelType } from "@/types/models";
import { cn } from "@/utils/utils";
import { sameModel } from "./modelOverrideUtils";
import { useModelOptions } from "./useModelOptions";

interface ModelOverrideRowProps {
  flowId: string;
  /** The model version the row belongs to; keeps ids unique when versions are compared. */
  version: number;
  picker: FlowModelPicker;
  kind: ModelType;
  chosen: ModelSelection | undefined;
  onChange: (value: ModelSelection | null) => void;
}

export default function ModelOverrideRow({
  flowId,
  version,
  picker,
  kind,
  chosen,
  onChange,
}: ModelOverrideRowProps) {
  const { t } = useTranslation();
  const { options, ready } = useModelOptions(flowId, true, kind);
  const id = `model-override-${version}-${picker.node_id}-${picker.field}`;
  const value = chosen ?? picker.value;
  // A required picker saved empty in the flow: the run needs a model chosen here.
  const unset = picker.value.length === 0;
  const missing = unset && !chosen?.[0];
  const changed = !unset && !sameModel(value, picker.value);
  const hintId = `${id}-hint`;
  const label =
    picker.display_name === picker.component
      ? picker.component
      : `${picker.component} · ${picker.display_name}`;

  return (
    <div className="flex flex-col gap-2" data-testid={id}>
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={id} className="truncate">
          {label}
        </Label>
        {changed && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs normal-case text-muted-foreground"
            onClick={() => onChange(null)}
            ignoreTitleCase
            data-testid={`${id}-reset`}
          >
            {t("evals.evaluate.modelReset", {
              model: picker.value[0]?.name,
            })}
          </Button>
        )}
      </div>
      <div
        className={cn(
          "[&_button]:h-9",
          missing && "rounded-md ring-1 ring-destructive",
        )}
      >
        <ModelInputComponent
          id={id}
          value={value.map((model) => ({
            ...model,
            icon: model.icon ?? "Bot",
          }))}
          editNode={false}
          disabled={!ready}
          handleOnNewValue={({ value: next }) => onChange(next ?? null)}
          options={options}
          providerScope={{ flowId }}
          modelType={kind}
          showEmptyState
          aria-label={label}
        />
      </div>
      {unset && (
        <p
          id={hintId}
          className={cn(
            "text-xs",
            missing ? "text-destructive" : "text-muted-foreground",
          )}
          data-testid={`${id}-unset`}
        >
          {t("evals.evaluate.modelUnset")}
        </p>
      )}
    </div>
  );
}
