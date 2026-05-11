import { Button } from "@/components/ui/button";
import {
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "@/components/ui/dialog";
import StepDeployStatus from "@/pages/MainPage/pages/deploymentsPage/components/step-deploy-status";

interface UpdatePhaseContentProps {
  isUpdating: boolean;
  isUpdated: boolean;
  deploymentName: string;
  onClose: () => void;
  onTest?: () => void;
}

export default function UpdatePhaseContent({
  isUpdating,
  isUpdated,
  deploymentName,
  onClose,
  onTest,
}: UpdatePhaseContentProps) {
  return (
    <>
      <DialogTitle className="sr-only">
        {isUpdating ? "Updating deployment" : "Deployment updated"}
      </DialogTitle>
      <DialogDescription className="sr-only">
        {isUpdating
          ? "Your deployment is being updated."
          : `"${deploymentName}" has been updated.`}
      </DialogDescription>
      <StepDeployStatus
        phase={isUpdating ? "deploying" : "deployed"}
        deploymentName={deploymentName}
        loadingTitle="Updating..."
        loadingDescription="Your deployment is being updated. This usually takes a few seconds."
        doneTitle="Deployment updated"
        doneDescription={`"${deploymentName}" has been updated successfully.`}
      />
      {isUpdated && (
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          {onTest && <Button onClick={onTest}>Test</Button>}
        </DialogFooter>
      )}
    </>
  );
}
