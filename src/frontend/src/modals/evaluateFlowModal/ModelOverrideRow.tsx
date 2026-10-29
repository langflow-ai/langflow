import { useTranslation } from "react-i18next";
import ModelInputComponent from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type {
  FlowModelPicker,
  ModelSelection,
} from "@/controllers/API/queries/evals/types";
import type { ModelType } from "@/types/models";
import { sameModel } from "./modelOverrideUtils";
import { useModelOptions } from "./useModelOptions";

interface ModelOverrideRowProps {
  flowId: string;
  picker: FlowModelPicker;
  kind: ModelType;
  chosen: ModelSelection | undefined;
  onChange: (value: ModelSelection | null) => void;
}

export default function ModelOverrideRow({
  flowId,
  picker,
  kind,
  chosen,
  onChange,
}: ModelOverrideRowProps) {
  const { t } = useTranslation();
  const { options, ready } = useModelOptions(flowId, true, kind);
  const id = `model-override-${picker.node_id}-${picker.field}`;
  const value = chosen ?? picker.value;
  const changed = !sameModel(value, picker.value);
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
            data-testid={`${id}-reset`}
          >
            {t("evals.evaluate.modelReset", {
              model: picker.value[0]?.name,
            })}
          </Button>
        )}
      </div>
      <div className="[&_button]:h-9">
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
    </div>
  );
}
