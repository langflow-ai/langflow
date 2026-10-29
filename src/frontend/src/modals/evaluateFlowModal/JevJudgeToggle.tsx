import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import ModelProviderModal from "@/modals/modelProviderModal";

export const JEV_PROVIDER = "TypeSafe";
export const JEV_MODEL: ModelOption = {
  id: "jev-latest",
  name: "jev-latest",
  provider: JEV_PROVIDER,
  icon: "Bot",
  metadata: { model_type: "decision" },
};

export function isJevModel(model: ModelOption | undefined): boolean {
  return model?.provider === JEV_PROVIDER;
}

interface JevJudgeToggleProps {
  flowId: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

/** Judge with TypeSafe's Jev decision model instead of a generating model from Model Providers. */
export default function JevJudgeToggle({
  flowId,
  checked,
  onChange,
}: JevJudgeToggleProps) {
  const { t } = useTranslation();
  const [managing, setManaging] = useState(false);
  const { data: providers, isSuccess } = useGetModelProviders(
    { flowId, purpose: "use" },
    { enabled: checked && Boolean(flowId) },
  );
  const configured = providers?.some(
    (provider) => provider.provider === JEV_PROVIDER && provider.is_configured,
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-start gap-2">
        <Checkbox
          id="judge-use-jev"
          data-testid="judge-use-jev"
          checked={checked}
          onCheckedChange={(next) => onChange(next === true)}
          aria-describedby="judge-use-jev-hint"
          className="mt-0.5"
        />
        <div className="flex flex-col gap-0.5">
          <Label htmlFor="judge-use-jev" className="font-normal">
            {t("evals.jev.label")}
          </Label>
          <span
            id="judge-use-jev-hint"
            className="text-xs text-muted-foreground"
          >
            {t("evals.jev.hint")}
          </span>
        </div>
      </div>
      {checked && isSuccess && !configured && (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-dashed px-3 py-2 text-xs"
          data-testid="judge-jev-missing-key"
        >
          <span>{t("evals.jev.missingKey")}</span>
          <Button
            variant="outline"
            size="sm"
            className="h-7 normal-case"
            onClick={() => setManaging(true)}
          >
            {t("evals.jev.addKey")}
          </Button>
        </div>
      )}
      {managing && (
        <ModelProviderModal
          open={managing}
          onClose={() => setManaging(false)}
          modelType="decision"
          flowId={flowId}
        />
      )}
    </div>
  );
}
