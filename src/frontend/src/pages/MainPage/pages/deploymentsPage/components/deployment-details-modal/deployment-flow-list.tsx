import type { DeploymentFlowVersionItem } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";
import FlowVersionItem from "./flow-version-item";

interface DeploymentFlowListProps {
  flowVersions: DeploymentFlowVersionItem[];
  getConnectionNames: (fv: DeploymentFlowVersionItem) => string[];
}

export default function DeploymentFlowList({
  flowVersions,
  getConnectionNames,
}: DeploymentFlowListProps) {
  return (
    <div className="flex flex-col gap-3">
      <span className="text-sm font-medium text-foreground">
        Attached Flows ({flowVersions.length})
      </span>
      {flowVersions.length === 0 ? (
        <span className="text-sm text-muted-foreground">No flows attached</span>
      ) : (
        <div className="flex flex-col gap-2">
          {flowVersions.map((fv) => (
            <FlowVersionItem
              key={fv.id}
              flowName={fv.flow_name}
              versionNumber={fv.version_number}
              toolName={fv.provider_data?.tool_name ?? null}
              connectionNames={getConnectionNames(fv)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
