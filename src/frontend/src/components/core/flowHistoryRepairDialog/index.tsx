import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  // Escape and the close button do what Cancel does, and like Cancel they
  // wait while a repair runs.
  const handleCancel = () => {
    if (!isRepairing) setProblem(null);
  };

  return (
    <Dialog open onOpenChange={(open) => !open && handleCancel()}>
      <DialogContent
        className="max-w-md"
        // A click beside the dialog is not a choice.
        onInteractOutside={(event) => event.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 pr-6 leading-normal">
            <ForwardedIconComponent
              name="TriangleAlert"
              className="h-5 w-5 text-accent-amber-foreground"
            />
            {isMismatch
              ? t("flowHistory.repair.mismatchTitle")
              : t("flowHistory.repair.invalidTitle")}
          </DialogTitle>
        </DialogHeader>
        <DialogDescription>
          {isMismatch
            ? t("flowHistory.repair.mismatchBody")
            : problem.graph === "stored"
              ? t("flowHistory.repair.invalidStoredBody")
              : t("flowHistory.repair.invalidSubmittedBody")}
        </DialogDescription>
        {!isMismatch && problem.violations && problem.violations.length > 0 && (
          <ul className="list-disc pl-5 text-xs text-muted-foreground">
            {problem.violations.map((code) => (
              <li key={code}>{t(`flowHistory.violation.${code}`)}</li>
            ))}
          </ul>
        )}
        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCancel}
            disabled={isRepairing}
          >
            {t("flowHistory.repair.cancel")}
          </Button>
          <Button size="sm" onClick={handleRepair} loading={isRepairing}>
            {t("flowHistory.repair.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
