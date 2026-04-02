import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useFolderStore } from "@/stores/foldersStore";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";

export default function StepReview() {
  const {
    isEditMode,
    editingDeployment,
    deploymentType,
    deploymentName,
    selectedLlm,
    connections,
    selectedVersionByFlow,
    toolNameByFlow,
    attachedExistingTools,
    attachedConnectionByFlow,
    removedFlowIds,
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

  // Build review items — one per tool (one tool per flow)
  const reviewTools = Array.from(selectedVersionByFlow.entries()).map(
    ([flowId, { versionId, versionTag }]) => {
      const flow = allFlows.find((f) => f.id === flowId);
      const flowName = flow?.name ?? "Unknown";
      const toolName = toolNameByFlow.get(flowId) || flowName;
      const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
      const flowConnections = connectionIds
        .map((cid) => connections.find((c) => c.id === cid))
        .filter((c): c is (typeof connections)[number] => c != null);

      const seenKeys = new Set<string>();
      const envVars: Array<{ key: string; masked: string }> = [];
      for (const conn of flowConnections) {
        if (conn.environmentVariables) {
          for (const key of Object.keys(conn.environmentVariables)) {
            if (!seenKeys.has(key)) {
              seenKeys.add(key);
              envVars.push({ key, masked: "••••••••" });
            }
          }
        }
      }

      return {
        flowId,
        flowName,
        toolName,
        versionLabel: versionTag || versionId,
        connectionNames: flowConnections.map((c) => c.name),
        envVars,
      };
    },
  );

  return (
    <div className="flex flex-col gap-4 py-3">
      <div>
        <h2 className="text-lg font-semibold">Review & Confirm</h2>
        <p className="text-sm text-muted-foreground">
          {isEditMode
            ? "Review your changes before updating."
            : "Review your deployment details before creating."}
        </p>
      </div>

      {/* Deployment info */}
      <div className="rounded-xl border border-border bg-background p-4">
        <div className="flex flex-col gap-3">
          <span className="text-sm font-medium text-foreground">
            Deployment
          </span>
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <span className="w-12 text-xs text-muted-foreground">Type</span>
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
            <div className="flex items-center gap-2">
              <span className="w-12 text-xs text-muted-foreground">Name</span>
              <span className="text-sm text-foreground">
                {deploymentName || "—"}
              </span>
            </div>
            {selectedLlm && (
              <div className="flex items-center gap-2">
                <span className="w-12 text-xs text-muted-foreground">
                  Model
                </span>
                <span className="text-sm text-foreground">{selectedLlm}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tools section */}
      <div className="rounded-xl border border-border bg-background p-4">
        <div className="flex flex-col gap-3">
          <span className="text-sm font-medium text-foreground">Tools</span>
          {reviewTools.length === 0 && attachedExistingTools.size === 0 ? (
            <span className="text-sm text-muted-foreground">
              No tools attached
            </span>
          ) : (
            <div className="flex flex-col gap-3">
              {reviewTools.map((item) => (
                <div
                  key={item.flowId}
                  className="rounded-lg border border-border bg-muted/30 p-3"
                >
                  <div className="flex flex-col gap-2">
                    {/* Tool name */}
                    <div className="flex items-center gap-2">
                      <ForwardedIconComponent
                        name="Wrench"
                        className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                      />
                      <span className="text-sm font-medium text-foreground">
                        {item.toolName}
                      </span>
                    </div>

                    {/* Attached flow */}
                    <div className="flex items-center gap-2 pl-5">
                      <ForwardedIconComponent
                        name="Workflow"
                        className="h-3 w-3 shrink-0 text-muted-foreground"
                      />
                      <span className="text-xs text-muted-foreground">
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

                    {/* Connections */}
                    {item.connectionNames.length > 0 && (
                      <div className="flex items-center gap-2 pl-5">
                        <ForwardedIconComponent
                          name="Plug"
                          className="h-3 w-3 shrink-0 text-muted-foreground"
                        />
                        <span className="text-xs text-muted-foreground">
                          {item.connectionNames.join(", ")}
                        </span>
                      </div>
                    )}

                    {/* Env vars */}
                    {item.envVars.length > 0 && (
                      <div className="mt-1 flex flex-col divide-y divide-border overflow-hidden rounded-md border border-border">
                        {item.envVars.map(({ key, masked }) => (
                          <div
                            key={key}
                            className="flex items-center justify-between bg-muted/40 px-3 py-1.5"
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
                    )}
                  </div>
                </div>
              ))}
              {/* Existing provider tools */}
              {Array.from(attachedExistingTools.entries()).map(
                ([toolId, toolName]) => (
                  <div
                    key={toolId}
                    className="rounded-lg border border-border bg-muted/30 p-3"
                  >
                    <div className="flex items-center gap-2">
                      <ForwardedIconComponent
                        name="Wrench"
                        className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                      />
                      <span className="text-sm font-medium text-foreground">
                        {toolName}
                      </span>
                      <Badge
                        variant="secondaryStatic"
                        size="tag"
                        className="bg-muted text-muted-foreground"
                      >
                        existing
                      </Badge>
                    </div>
                  </div>
                ),
              )}
            </div>
          )}
        </div>
      </div>

      {/* Detaching section — only in edit mode when flows are being removed */}
      {isEditMode && removedFlowIds.size > 0 && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium text-destructive">
              Detaching
            </span>
            <div className="flex flex-col gap-2">
              {Array.from(removedFlowIds).map((flowId) => {
                const flow = allFlows.find((f) => f.id === flowId);
                const flowName = flow?.name ?? "Unknown flow";
                const removedToolName = toolNameByFlow.get(flowId);
                return (
                  <div
                    key={flowId}
                    className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-background p-3"
                  >
                    <ForwardedIconComponent
                      name="Wrench"
                      className="h-3.5 w-3.5 shrink-0 text-destructive/60"
                    />
                    <span className="text-sm text-foreground">
                      {removedToolName || flowName}
                    </span>
                    <Badge
                      variant="secondaryStatic"
                      size="tag"
                      className="bg-destructive/10 text-destructive"
                    >
                      removing
                    </Badge>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground">
              These tools will be detached from the agent. They will remain
              available on your provider tenant.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
