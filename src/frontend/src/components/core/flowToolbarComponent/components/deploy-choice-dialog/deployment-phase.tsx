import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type {
  Deployment,
  ProviderAccount,
} from "@/pages/MainPage/pages/deploymentsPage/types";

const NEW_DEPLOYMENT_VALUE = "__new__";

interface DeploymentPhaseContentProps {
  selectedProvider: ProviderAccount | null;
  deployments: Deployment[];
  selectedDeployment: string;
  onSelectDeployment: (id: string) => void;
  isLoading: boolean;
  isBusy: boolean;
  showBack: boolean;
  onBack: () => void;
  onContinue: () => void;
  onCancel: () => void;
}

export { NEW_DEPLOYMENT_VALUE };

export default function DeploymentPhaseContent({
  selectedProvider,
  deployments,
  selectedDeployment,
  onSelectDeployment,
  isLoading,
  isBusy,
  showBack,
  onBack,
  onContinue,
  onCancel,
}: DeploymentPhaseContentProps) {
  return (
    <>
      <DialogHeader>
        <DialogTitle>Select Deployment</DialogTitle>
        <DialogDescription>
          {selectedProvider
            ? `Deployments on ${selectedProvider.name} for this flow.`
            : "Select a deployment to update or create a new one."}
        </DialogDescription>
      </DialogHeader>

      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <ForwardedIconComponent
            name="Loader2"
            className="h-5 w-5 animate-spin text-muted-foreground"
          />
        </div>
      ) : (
        <RadioGroup
          value={selectedDeployment}
          onValueChange={onSelectDeployment}
        >
          {deployments.map((deployment) => (
            <div
              key={deployment.id}
              className="flex items-center gap-3 rounded-lg border p-3"
            >
              <RadioGroupItem
                value={deployment.id}
                id={`deploy-${deployment.id}`}
              />
              <Label
                htmlFor={`deploy-${deployment.id}`}
                className="flex flex-1 cursor-pointer flex-col gap-0.5"
              >
                <span className="text-sm font-medium">{deployment.name}</span>
                <span className="text-xs text-muted-foreground">
                  {deployment.type} deployment
                </span>
              </Label>
            </div>
          ))}

          <div className="flex items-center gap-3 rounded-lg border p-3">
            <RadioGroupItem value={NEW_DEPLOYMENT_VALUE} id="deploy-new" />
            <Label
              htmlFor="deploy-new"
              className="flex flex-1 cursor-pointer flex-col gap-0.5"
            >
              <span className="text-sm font-medium">Create new deployment</span>
              <span className="text-xs text-muted-foreground">
                {selectedProvider
                  ? `New deployment on ${selectedProvider.name}`
                  : "Set up a new deployment from scratch"}
              </span>
            </Label>
          </div>
        </RadioGroup>
      )}

      <div className="flex items-center justify-between pt-4">
        <Button variant="ghost" onClick={onCancel} disabled={isBusy}>
          Cancel
        </Button>
        <div className="flex items-center gap-3">
          {showBack && (
            <Button variant="outline" onClick={onBack} disabled={isBusy}>
              Back
            </Button>
          )}
          <Button onClick={onContinue} disabled={isBusy}>
            Continue
          </Button>
        </div>
      </div>
    </>
  );
}
