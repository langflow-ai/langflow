import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type {
  FlowModelPicker,
  ModelSelection,
} from "@/controllers/API/queries/evals/types";
import VariantMarker from "@/pages/MainPage/pages/evalsPage/components/VariantMarker";
import type { ModelType } from "@/types/models";
import ModelOverrideRow from "./ModelOverrideRow";
import { type ChosenModels, pickerKey } from "./modelOverrideUtils";

interface ModelVersionCardProps {
  flowId: string;
  version: number;
  rows: readonly { picker: FlowModelPicker; kind: ModelType }[];
  chosen: ChosenModels;
  summary: string;
  canDuplicate: boolean;
  onChange: (key: string, value: ModelSelection | null) => void;
  onDuplicate: () => void;
  onRemove: () => void;
}

/** One model version of a comparison: the flow's model pickers, set for this version only. */
export default function ModelVersionCard({
  flowId,
  version,
  rows,
  chosen,
  summary,
  canDuplicate,
  onChange,
  onDuplicate,
  onRemove,
}: ModelVersionCardProps) {
  const { t } = useTranslation();
  const title = t("evals.compare.version", { number: version + 1 });
  const headingId = `model-version-${version}-title`;

  return (
    <section
      aria-labelledby={headingId}
      className="flex min-w-0 flex-col gap-3 rounded-lg border p-3"
      data-testid={`model-version-${version}`}
    >
      <div className="flex items-center gap-2">
        <VariantMarker index={version} />
        <h4 id={headingId} className="text-sm font-medium">
          {title}
        </h4>
        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
          {summary}
        </span>
        <Button
          variant="ghost"
          size="iconMd"
          onClick={onDuplicate}
          disabled={!canDuplicate}
          aria-label={t("evals.compare.duplicate", { version: title })}
          data-testid={`model-version-${version}-duplicate`}
        >
          <ForwardedIconComponent name="Copy" className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="iconMd"
          onClick={onRemove}
          aria-label={t("evals.compare.remove", { version: title })}
          data-testid={`model-version-${version}-remove`}
        >
          <ForwardedIconComponent name="X" className="h-4 w-4" />
        </Button>
      </div>
      {rows.map(({ picker, kind }) => (
        <ModelOverrideRow
          key={pickerKey(picker)}
          flowId={flowId}
          version={version}
          picker={picker}
          kind={kind}
          chosen={chosen[pickerKey(picker)]}
          onChange={(value) => onChange(pickerKey(picker), value)}
        />
      ))}
    </section>
  );
}
