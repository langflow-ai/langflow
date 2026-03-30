import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useFolderStore } from "@/stores/foldersStore";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";

export default function StepReview() {
  const {
    deploymentType,
    deploymentName,
    connections,
    selectedVersionByFlow,
    attachedConnectionByFlow,
  } = useDeploymentStepper();

  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const currentFolderId = folderId ?? myCollectionId;

  const { data: flowsData } = useGetRefreshFlowsQuery(
    {
      get_all: true,
      remove_example_flows: true,
    },
    { enabled: !!currentFolderId },
  );
  const allFlows = (Array.isArray(flowsData) ? flowsData : []).filter(
    (f) => f.folder_id === currentFolderId,
  );

  const reviewFlows = Array.from(selectedVersionByFlow.entries()).map(
    ([flowId, { versionId, versionTag }]) => {
      const flow = allFlows.find((f) => f.id === flowId);
      return {
        flowId,
        flowName: flow?.name ?? "Unknown",
        versionLabel: versionTag || versionId,
      };
    },
  );

  // Collect all env vars from attached connections across all flows
  const allEnvVars: Array<{ key: string; masked: string }> = [];
  const seenKeys = new Set<string>();
  Array.from(attachedConnectionByFlow.values()).forEach((connectionIds) => {
    connectionIds.forEach((cid) => {
      const conn = connections.find((c) => c.id === cid);
      if (conn?.environmentVariables) {
        Object.keys(conn.environmentVariables).forEach((key) => {
          if (!seenKeys.has(key)) {
            seenKeys.add(key);
            allEnvVars.push({ key, masked: "••••••••" });
          }
        });
      }
    });
  });

  return (
    <div className="flex flex-col gap-4 py-3">
      <div>
        <h2 className="text-lg font-semibold">Review & Confirm</h2>
        <p className="text-sm text-muted-foreground">
          Review your deployment details before creating.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-background p-4">
        <div className="grid grid-cols-2 gap-6">
          {/* Deployment column */}
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium text-foreground">
              Deployment
            </span>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <span className="w-10 text-xs text-muted-foreground">Type</span>
                <div className="flex items-center gap-1.5">
                  <ForwardedIconComponent
                    name={deploymentType === "agent" ? "Bot" : "Server"}
                    className="h-3.5 w-3.5 text-muted-foreground"
                  />
                  <span className="text-sm text-foreground capitalize">
                    {deploymentType}
                  </span>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-10 text-xs text-muted-foreground">Name</span>
                <span className="text-sm text-foreground">
                  {deploymentName || "—"}
                </span>
              </div>
            </div>
          </div>

          {/* Attached Flows column */}
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium text-foreground">
              Attached Flows
            </span>
            <div className="flex flex-col gap-1.5">
              {reviewFlows.length === 0 ? (
                <span className="text-sm text-muted-foreground">—</span>
              ) : (
                reviewFlows.map((item) => (
                  <div key={item.flowId} className="flex items-center gap-1.5">
                    <ForwardedIconComponent
                      name="Link"
                      className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                    />
                    <span className="text-sm text-foreground">
                      {item.flowName}
                    </span>
                    <Badge
                      variant="secondaryStatic"
                      size="tag"
                      className="bg-accent-purple-muted text-accent-purple-muted-foreground"
                    >
                      {item.versionLabel}
                    </Badge>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Configuration section */}
      {allEnvVars.length > 0 && (
        <div className="rounded-xl border border-border bg-background p-4">
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium text-foreground">
              Configuration
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                Env Variables
              </span>
              <span className="text-xs text-foreground">
                {allEnvVars.length}{" "}
                {allEnvVars.length === 1 ? "variable" : "variables"}
              </span>
            </div>
            <div className="flex flex-col divide-y divide-border overflow-hidden rounded-lg border border-border">
              {allEnvVars.map(({ key, masked }) => (
                <div
                  key={key}
                  className="flex items-center justify-between bg-muted/40 px-3 py-2"
                >
                  <span className="font-mono text-xs text-foreground">
                    {key}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">=</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      {masked}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
