import { useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import useFlowHistoryRepairStore from "@/stores/flowHistoryRepairStore";

/**
 * Offers to repair a flow whose save the server refused for a reason it can fix.
 *
 * A flow edited outside Langflow no longer matches its history; repairing
 * resets it to the latest recorded version before saving. A flow that breaks
 * the flow graph rules (an edge to a missing component, duplicate IDs) is
 * repaired and saved, and the stored original is kept as a version.
 */
export default function FlowHistoryRepairDialog() {
  const { t } = useTranslation();
  const problem = useFlowHistoryRepairStore((state) => state.problem);
  const setProblem = useFlowHistoryRepairStore((state) => state.setProblem);
  const [isRepairing, setIsRepairing] = useState(false);

  if (!problem) return null;

  const isMismatch = problem.code === "FLOW_REVISION_MISMATCH";
  const handleRepair = async () => {
    setIsRepairing(true);
    try {
      await problem.repair();
      setProblem(null);
    } finally {
      setIsRepairing(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div
        role="alertdialog"
        aria-labelledby="flow-history-repair-title"
        className="mx-4 flex w-full max-w-md flex-col gap-4 rounded-xl border bg-background p-6 shadow-lg"
      >
        <div className="flex items-center gap-2">
          <ForwardedIconComponent
            name="TriangleAlert"
            className="h-5 w-5 text-accent-amber-foreground"
          />
          <span
            id="flow-history-repair-title"
            className="text-lg font-semibold"
          >
            {isMismatch
              ? t("flowHistory.repair.mismatchTitle")
              : t("flowHistory.repair.invalidTitle")}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          {isMismatch
            ? t("flowHistory.repair.mismatchBody")
            : problem.graph === "stored"
              ? t("flowHistory.repair.invalidStoredBody")
              : t("flowHistory.repair.invalidSubmittedBody")}
        </p>
        {!isMismatch && problem.violations && problem.violations.length > 0 && (
          <ul className="list-disc pl-5 text-xs text-muted-foreground">
            {problem.violations.map((code) => (
              <li key={code}>{t(`flowHistory.violation.${code}`)}</li>
            ))}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setProblem(null)}
            disabled={isRepairing}
          >
            {t("flowHistory.repair.cancel")}
          </Button>
          <Button size="sm" onClick={handleRepair} loading={isRepairing}>
            {t("flowHistory.repair.confirm")}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
