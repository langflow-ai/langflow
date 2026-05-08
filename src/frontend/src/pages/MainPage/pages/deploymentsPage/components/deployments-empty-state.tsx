import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

interface DeploymentsEmptyStateProps {
  onAction: () => void;
}

export default function DeploymentsEmptyState({
  onAction,
}: DeploymentsEmptyStateProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <h3 className="text-lg font-semibold">
        {t("deployments.noDeployments")}
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        {t("deployments.emptyStateDescription")}
      </p>
      <Button
        variant="outline"
        className="mt-4"
        data-testid="create-deployment-empty-btn"
        onClick={onAction}
      >
        <ForwardedIconComponent name="Plus" className="h-4 w-4" />
        {t("deployments.createDeployment")}
      </Button>
    </div>
  );
}
