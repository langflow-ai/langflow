import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyDescription,
  EmptyTitle,
} from "@/components/ui/empty-state";

interface DeploymentsEmptyStateProps {
  onAction: () => void;
}

export default function DeploymentsEmptyState({
  onAction,
}: DeploymentsEmptyStateProps) {
  const { t } = useTranslation();
  return (
    <Empty className="py-24">
      <EmptyTitle className="text-lg">
        {t("deployments.noDeployments")}
      </EmptyTitle>
      <EmptyDescription className="mt-1 text-sm text-muted-foreground">
        {t("deployments.emptyStateDescription")}
      </EmptyDescription>
      <Button
        variant="outline"
        className="mt-4"
        data-testid="create-deployment-empty-btn"
        onClick={onAction}
      >
        <ForwardedIconComponent name="Plus" className="h-4 w-4" />
        {t("deployments.createDeployment")}
      </Button>
    </Empty>
  );
}
