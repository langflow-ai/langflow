import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";

interface DeploymentSuccessContentProps {
  deploymentName?: string;
  providerName: string;
  providerUrl: string;
  showTestButton: boolean;
  onTest: () => void;
}

export default function DeploymentSuccessContent({
  deploymentName,
  providerName,
  providerUrl,
  showTestButton,
  onTest,
}: DeploymentSuccessContentProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 py-10 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full border-2 border-emerald-500">
        <ForwardedIconComponent
          name="Check"
          className="h-8 w-8 text-emerald-500"
        />
      </div>

      <div className="space-y-2">
        <h3 className="font-sans text-2xl font-semibold tracking-normal text-foreground">
          Deployment successful
        </h3>
        <p className="font-sans text-base font-normal text-muted-foreground">
          Deployed to {providerName} as draft
        </p>
      </div>

      <div className="flex items-center gap-1 font-sans text-sm font-normal text-muted-foreground">
        <span>Publish from Draft to Live in</span>
        <a
          href={providerUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 font-semibold text-foreground hover:underline"
        >
          {providerName}
          <ForwardedIconComponent name="ArrowUpRight" className="h-4 w-4" />
        </a>
      </div>

      {showTestButton && deploymentName && (
        <Button
          variant="outline"
          className="h-11 w-full max-w-lg gap-2 rounded-lg border-zinc-700 font-sans text-base font-semibold text-foreground hover:bg-input"
          data-testid="deployment-stepper-test"
          onClick={onTest}
        >
          <ForwardedIconComponent name="Play" className="h-5 w-5" />
          Test Deployment
        </Button>
      )}
    </div>
  );
}
