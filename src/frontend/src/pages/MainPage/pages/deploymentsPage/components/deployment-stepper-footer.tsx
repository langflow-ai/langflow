import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

interface DeploymentStepperFooterProps {
  canGoNext: boolean;
  currentStep: number;
  isCreatingAccount: boolean;
  isDeployed: boolean;
  isDeploying: boolean;
  isInDeployPhase: boolean;
  isFinalStep: boolean;
  minStep: number;
  actionIcon: string;
  actionLabel: string;
  progressLabel: string;
  onBack: () => void;
  onCancel: () => void;
  onClose: () => void;
  onPrimaryAction: () => void;
}

export default function DeploymentStepperFooter({
  canGoNext,
  currentStep,
  isCreatingAccount,
  isDeployed,
  isDeploying,
  isInDeployPhase,
  isFinalStep,
  minStep,
  actionIcon,
  actionLabel,
  progressLabel,
  onBack,
  onCancel,
  onClose,
  onPrimaryAction,
}: DeploymentStepperFooterProps) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-between border-t border-border px-6 py-4">
      {isDeployed ? (
        <div />
      ) : (
        <Button variant="ghost" onClick={onCancel}>
          {t("deployments.cancel")}
        </Button>
      )}
      <div className="flex items-center gap-3">
        {!isDeployed && (
          <Button
            variant="outline"
            onClick={onBack}
            disabled={currentStep === minStep || isDeploying}
          >
            {t("deployments.back")}
          </Button>
        )}
        {!isInDeployPhase && (
          <Button
            onClick={onPrimaryAction}
            disabled={!canGoNext || isCreatingAccount}
            data-testid="deployment-stepper-next"
          >
            {isFinalStep ? (
              <>
                <ForwardedIconComponent name={actionIcon} className="h-4 w-4" />
                {actionLabel}
              </>
            ) : isCreatingAccount ? (
              t("deployments.connecting")
            ) : (
              t("deployments.next")
            )}
          </Button>
        )}
        {isDeploying && (
          <Button disabled data-testid="deployment-stepper-next">
            <ForwardedIconComponent
              name={actionIcon}
              className="h-4 w-4 animate-pulse"
            />
            {progressLabel}
          </Button>
        )}
        {isDeployed && (
          <Button onClick={onClose}>{t("deployments.done")}</Button>
        )}
      </div>
    </div>
  );
}
