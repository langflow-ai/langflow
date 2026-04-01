import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

interface DeploymentsEmptyStateProps {
  onCreateDeployment: () => void;
}

export default function DeploymentsEmptyState({
  onCreateDeployment,
}: DeploymentsEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <h3 className="text-lg font-semibold">No Deployments</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Create your first deployment to run your flows in production.
      </p>
      <Button
        variant="outline"
        className="mt-4"
        data-testid="create-deployment-empty-btn"
        onClick={onCreateDeployment}
      >
        <ForwardedIconComponent name="Plus" className="h-4 w-4" />
        Create Deployment
      </Button>
    </div>
  );
}
