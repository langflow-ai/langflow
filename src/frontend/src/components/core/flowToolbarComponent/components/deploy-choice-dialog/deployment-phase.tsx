import { useTranslation } from "react-i18next";
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
import { getDeploymentDisplayName } from "@/pages/MainPage/pages/deploymentsPage/types";

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
  const { t } = useTranslation();
  return (
    <>
      <DialogHeader>
        <DialogTitle>{t("deployments.selectDeployment")}</DialogTitle>
        <DialogDescription>
          {selectedProvider
            ? t("deployments.deploymentsOnProvider", {
                name: selectedProvider.name,
              })
            : t("deployments.selectDeploymentDescription")}
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
          {deployments.map((deployment) => {
            const displayName = getDeploymentDisplayName(deployment);
            return (
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
                  <span className="text-sm font-medium">{displayName}</span>
                  <span className="text-xs text-muted-foreground">
                    {deployment.type} deployment
                  </span>
                </Label>
              </div>
            );
          })}

          <div className="flex items-center gap-3 rounded-lg border p-3">
            <RadioGroupItem value={NEW_DEPLOYMENT_VALUE} id="deploy-new" />
            <Label
              htmlFor="deploy-new"
              className="flex flex-1 cursor-pointer flex-col gap-0.5"
            >
              <span className="text-sm font-medium">
                {t("deployments.createNewDeployment")}
              </span>
              <span className="text-xs text-muted-foreground">
                {selectedProvider
                  ? t("deployments.newDeploymentOnProvider", {
                      name: selectedProvider.name,
                    })
                  : t("deployments.setupNewDeployment")}
              </span>
            </Label>
          </div>
        </RadioGroup>
      )}

      <div className="flex items-center justify-between pt-4">
        <Button variant="ghost" onClick={onCancel} disabled={isBusy}>
          {t("deployments.cancel")}
        </Button>
        <div className="flex items-center gap-3">
          {showBack && (
            <Button variant="outline" onClick={onBack} disabled={isBusy}>
              {t("deployments.back")}
            </Button>
          )}
          <Button onClick={onContinue} disabled={isBusy}>
            {t("deployments.continue")}
          </Button>
        </div>
      </div>
    </>
  );
}
