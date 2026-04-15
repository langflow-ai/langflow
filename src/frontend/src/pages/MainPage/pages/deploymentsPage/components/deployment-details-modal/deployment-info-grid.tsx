import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { Deployment } from "../../types";

interface DeploymentInfoGridProps {
  deployment: Deployment | null;
  providerName: string;
  llm: string;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function DeploymentInfoGrid({
  deployment,
  providerName,
  llm,
}: DeploymentInfoGridProps) {
  return (
    <div className="grid grid-cols-[auto_1fr_auto_1fr] items-baseline gap-x-3 gap-y-2">
      <span className="text-xs text-muted-foreground">Type</span>
      <div className="flex items-center gap-1.5">
        <ForwardedIconComponent
          name={deployment?.type === "agent" ? "Bot" : "Server"}
          className="h-3.5 w-3.5 text-muted-foreground"
        />
        <span className="text-sm text-foreground capitalize">
          {deployment?.type}
        </span>
      </div>
      <span className="text-xs text-muted-foreground">Created</span>
      <span className="text-sm text-foreground">
        {deployment?.created_at ? formatDate(deployment.created_at) : "—"}
      </span>

      <span className="text-xs text-muted-foreground">Name</span>
      <span className="text-sm text-foreground">{deployment?.name || "—"}</span>
      <span className="text-xs text-muted-foreground">Modified</span>
      <span className="text-sm text-foreground">
        {deployment?.updated_at ? formatDate(deployment.updated_at) : "—"}
      </span>

      {deployment?.description && (
        <>
          <span className="text-xs text-muted-foreground">Desc</span>
          <span className="col-span-3 text-sm text-foreground">
            {deployment.description}
          </span>
        </>
      )}

      {llm && (
        <>
          <span className="text-xs text-muted-foreground">Model</span>
          <span className="col-span-3 break-words text-sm text-foreground">
            {llm}
          </span>
        </>
      )}

      <span className="text-xs text-muted-foreground">Provider</span>
      <span className="col-span-3 text-sm text-foreground">
        {providerName || "—"}
      </span>
    </div>
  );
}
