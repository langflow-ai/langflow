import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { usePermissions } from "@/contexts/permissionsContext";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import EvaluateFlowModal from "@/modals/evaluateFlowModal";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import { cn } from "@/utils/utils";

const EvaluateButton = ({ hasIO }: { hasIO: boolean }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const { can } = usePermissions();
  const saveFlow = useSaveFlow();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const evalsEnabled = useUtilityStore(
    (state) => state.featureFlags.evals === true,
  );
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  if (!evalsEnabled || !currentFlowId) return null;
  const disabled = !hasIO || !can(currentFlowId, "execute") || saving;

  // "Latest" means the saved draft, and autosave is debounced; save first so the
  // checks and the run see exactly what is on the canvas; a failed save would evaluate a stale draft.
  const handleEvaluateClick = async () => {
    setSaving(true);
    try {
      await saveFlow(undefined, { suppressErrorToast: true });
      setOpen(true);
    } catch (error) {
      setErrorData({
        title: t("evals.evaluate.saveError"),
        list: extractApiErrorMessages(error),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <ShadTooltip
        side="bottom"
        align="end"
        content={
          hasIO ? t("evals.evaluate.tooltip") : t("evals.evaluate.needsIO")
        }
      >
        <div>
          <button
            type="button"
            disabled={disabled}
            onClick={handleEvaluateClick}
            aria-busy={saving}
            data-testid="evaluate-btn-flow"
            className={cn(
              "relative inline-flex h-8 items-center gap-1.5 rounded px-2 text-sm font-normal hover:bg-accent",
              "disabled:cursor-not-allowed disabled:text-muted-foreground disabled:hover:bg-transparent",
            )}
          >
            <ForwardedIconComponent
              name={saving ? "Loader2" : "FlaskConical"}
              className={cn("h-4 w-4", saving && "animate-spin")}
            />
            <span className="hidden font-normal text-mmd md:inline">
              {t("evals.evaluate.button")}
            </span>
          </button>
        </div>
      </ShadTooltip>
      {open && (
        <EvaluateFlowModal
          open={open}
          setOpen={setOpen}
          flowId={currentFlowId}
        />
      )}
    </>
  );
};

export default EvaluateButton;
