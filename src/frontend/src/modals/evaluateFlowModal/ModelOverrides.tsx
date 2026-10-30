import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type {
  FlowModelPicker,
  ModelSelection,
} from "@/controllers/API/queries/evals/types";
import { modelKindOfField } from "@/utils/model-kind";
import { cn } from "@/utils/utils";
import ModelOverrideRow from "./ModelOverrideRow";
import ModelVersionCard from "./ModelVersionCard";
import {
  type ChosenModels,
  MAX_MODEL_VARIANTS,
  type ModelVersion,
  pickerKey,
  sameModel,
} from "./modelOverrideUtils";

interface ModelOverridesProps {
  flowId: string;
  pickers: readonly FlowModelPicker[];
  versions: readonly ModelVersion[];
  onChange: (
    version: number,
    key: string,
    value: ModelSelection | null,
  ) => void;
  onDuplicate: (version: number) => void;
  onRemove: (version: number) => void;
}

/**
 * The flow's model pickers, folded away: a run can try other models without editing the flow, and
 * two or more versions run the dataset once each so their results can be compared.
 */
export default function ModelOverrides({
  flowId,
  pickers,
  versions,
  onChange,
  onDuplicate,
  onRemove,
}: ModelOverridesProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const rows = pickers.flatMap((picker) => {
    const kind = modelKindOfField({ model_type: picker.model_type });
    return kind ? [{ picker, kind }] : [];
  });
  if (rows.length === 0) return null;
  const comparing = versions.length > 1;
  const changedIn = (chosen: ChosenModels) =>
    rows.filter(({ picker }) => {
      const value = chosen[pickerKey(picker)];
      return value !== undefined && !sameModel(value, picker.value);
    }).length;
  const describe = (chosen: ChosenModels) => {
    const changed = changedIn(chosen);
    return changed > 0
      ? t("evals.evaluate.modelsChanged", { count: changed })
      : t("evals.evaluate.modelsAsInFlow");
  };
  const summary = comparing
    ? t("evals.compare.comparing", { count: versions.length })
    : describe(versions[0]?.chosen ?? {});
  const atLimit = versions.length >= MAX_MODEL_VARIANTS;

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
          {comparing ? t("evals.compare.hint") : t("evals.evaluate.modelsHint")}
        </p>
        {comparing ? (
          <div className="grid gap-3 md:grid-cols-2">
            {versions.map(({ key, chosen }, version) => (
              <ModelVersionCard
                key={key}
                flowId={flowId}
                version={version}
                rows={rows}
                chosen={chosen}
                summary={describe(chosen)}
                canDuplicate={!atLimit}
                onChange={(key, value) => onChange(version, key, value)}
                onDuplicate={() => onDuplicate(version)}
                onRemove={() => onRemove(version)}
              />
            ))}
          </div>
        ) : (
          rows.map(({ picker, kind }) => (
            <ModelOverrideRow
              key={pickerKey(picker)}
              flowId={flowId}
              version={0}
              picker={picker}
              kind={kind}
              chosen={versions[0]?.chosen[pickerKey(picker)]}
              onChange={(value) => onChange(0, pickerKey(picker), value)}
            />
          ))
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            className="normal-case"
            onClick={() => onDuplicate(versions.length - 1)}
            disabled={atLimit}
            data-testid="model-version-add"
          >
            <ForwardedIconComponent name="Plus" className="h-4 w-4" />
            {comparing ? t("evals.compare.add") : t("evals.compare.start")}
          </Button>
          <span className="text-xs text-muted-foreground">
            {atLimit
              ? t("evals.compare.limit", { count: MAX_MODEL_VARIANTS })
              : comparing
                ? t("evals.compare.sequential")
                : t("evals.compare.startHint")}
          </span>
        </div>
      </div>
    </div>
  );
}
