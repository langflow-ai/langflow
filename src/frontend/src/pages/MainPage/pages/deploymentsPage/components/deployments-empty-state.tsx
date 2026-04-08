import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

interface DeploymentsEmptyStateProps {
  variant: "no-providers" | "no-deployments";
  onAction: () => void;
}

const copy = {
  "no-providers": {
    title: "No Environments",
    description: "Add an environment before creating deployments.",
    button: "Add Environment",
    icon: "Plus" as const,
    testId: "add-environment-empty-btn",
  },
  "no-deployments": {
    title: "No Deployments",
    description:
      "Create your first deployment to run your flows in production.",
    button: "Create Deployment",
    icon: "Plus" as const,
    testId: "create-deployment-empty-btn",
  },
};

export default function DeploymentsEmptyState({
  variant,
  onAction,
}: DeploymentsEmptyStateProps) {
  const { title, description, button, icon, testId } = copy[variant];

  return (
    <div className="flex flex-col items-center justify-center py-24">
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      <Button
        variant="outline"
        className="mt-4"
        data-testid={testId}
        onClick={onAction}
      >
        <ForwardedIconComponent name={icon} className="h-4 w-4" />
        {button}
      </Button>
    </div>
  );
}
