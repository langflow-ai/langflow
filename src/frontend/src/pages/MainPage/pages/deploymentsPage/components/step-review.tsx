import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useFolderStore } from "@/stores/foldersStore";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";

function EditableToolName({
  value,
  placeholder,
  onSave,
}: {
  value: string;
  placeholder: string;
  onSave: (name: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const confirm = useCallback(() => {
    onSave(draft);
    setEditing(false);
  }, [draft, onSave]);

  const cancel = useCallback(() => {
    setDraft(value);
    setEditing(false);
  }, [value]);

  if (editing) {
    return (
      <div className="flex items-center gap-1.5">
        <Input
          ref={inputRef}
          className="h-7 w-48 text-sm"
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={confirm}
          onKeyDown={(e) => {
            if (e.key === "Enter") confirm();
            if (e.key === "Escape") cancel();
          }}
          data-testid="tool-name-input"
        />
        <button
          type="button"
          onClick={confirm}
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          title="Confirm"
        >
          <ForwardedIconComponent name="Check" className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-sm font-medium text-foreground">
        {value || placeholder}
      </span>
      <button
        type="button"
        onClick={() => {
          setDraft(value);
          setEditing(true);
        }}
        className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        title="Edit tool name"
        data-testid="edit-tool-name"
      >
        <ForwardedIconComponent name="Pencil" className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export default function StepReview() {
  const {
    isEditMode,
    deploymentType,
    deploymentName,
    selectedLlm,
    connections,
    selectedVersionByFlow,
    toolNameByFlow,
    setToolNameByFlow,
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

  const reviewFlows = Array.from(selectedVersionByFlow.entries()).map(
    ([flowId, { versionId, versionTag }]) => {
      const flow = allFlows.find((f) => f.id === flowId);
      const connectionIds = attachedConnectionByFlow.get(flowId) ?? [];
      const flowConnections = connectionIds
        .map((cid) => connections.find((c) => c.id === cid))
        .filter((c): c is (typeof connections)[number] => c != null);

      const connectionDetails = flowConnections.map((conn) => {
        const envVars = conn.environmentVariables
          ? Object.keys(conn.environmentVariables).map((key) => ({
              key,
              masked: "••••••••",
            }))
          : [];
        return { name: conn.name, isNew: conn.isNew ?? false, envVars };
      });

      const flowName = flow?.name ?? "Unknown";
      return {
        flowId,
        flowName,
        toolName: toolNameByFlow.get(flowId)?.trim() || flowName,
        versionLabel: versionTag || versionId,
        connectionDetails,
      };
    },
  );

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
              <div className="flex items-center gap-2">
                <span className="w-10 text-xs text-muted-foreground">Name</span>
                <span className="text-sm text-foreground">
                  {deploymentName || "—"}
                </span>
              </div>
              {selectedLlm && (
                <div className="flex items-center gap-2">
                  <span className="w-10 text-xs text-muted-foreground">
                    Model
                  </span>
                  <span className="text-sm text-foreground">{selectedLlm}</span>
                </div>
              )}
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
                      name="Workflow"
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

      {/* Configuration section – scoped per flow */}
      {reviewFlows.length > 0 && (
        <div className="flex flex-col gap-3">
          {reviewFlows.map((item) => (
            <div
              key={item.flowId}
              className="rounded-xl border border-border bg-background p-4"
            >
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <ForwardedIconComponent
                      name="Wrench"
                      className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                    />
                    <EditableToolName
                      value={toolNameByFlow.get(item.flowId)?.trim() ?? ""}
                      placeholder={item.flowName}
                      onSave={(name) => {
                        setToolNameByFlow((prev) => {
                          const next = new Map(prev);
                          if (name.trim()) {
                            next.set(item.flowId, name.trim());
                          } else {
                            next.delete(item.flowId);
                          }
                          return next;
                        });
                      }}
                    />
                  </div>
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
                </div>

                {item.connectionDetails.length > 0 &&
                  (() => {
                    const newConns = item.connectionDetails.filter(
                      (c) => c.isNew,
                    );
                    const existingConns = item.connectionDetails.filter(
                      (c) => !c.isNew,
                    );
                    return (
                      <div className="flex flex-col gap-4">
                        {existingConns.length > 0 && (
                          <div className="flex flex-col gap-2">
                            <span className="text-xs font-medium text-muted-foreground">
                              Existing Connections
                            </span>
                            {existingConns.map((conn) => (
                              <span
                                key={conn.name}
                                className="text-xs font-medium text-foreground"
                              >
                                {conn.name}
                              </span>
                            ))}
                          </div>
                        )}
                        {newConns.length > 0 && (
                          <div className="flex flex-col gap-2">
                            <span className="text-xs font-medium text-muted-foreground">
                              New Connections
                            </span>
                            {newConns.map((conn) => (
                              <div
                                key={conn.name}
                                className="flex flex-col gap-1.5"
                              >
                                <span className="text-xs font-medium text-foreground">
                                  {conn.name}
                                </span>
                                {conn.envVars.length > 0 && (
                                  <div className="flex flex-col divide-y divide-border overflow-hidden rounded-md border border-border">
                                    {conn.envVars.map(({ key, masked }) => (
                                      <div
                                        key={key}
                                        className="flex items-center justify-between bg-muted/40 px-3 py-1.5"
                                      >
                                        <span className="font-mono text-xs text-foreground">
                                          {key}
                                        </span>
                                        <div className="flex items-center gap-2">
                                          <span className="text-muted-foreground">
                                            =
                                          </span>
                                          <span className="font-mono text-xs text-muted-foreground">
                                            {masked}
                                          </span>
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })()}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Existing provider tools */}
      {/* Detaching section (edit mode) */}
      {isEditMode && removedFlowIds.size > 0 && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium text-destructive">
              Detaching
            </span>
            <div className="flex flex-col gap-2">
              {Array.from(removedFlowIds).map((flowId) => {
                const flow = allFlows.find((f) => f.id === flowId);
                return (
                  <div
                    key={flowId}
                    className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-background p-3"
                  >
                    <ForwardedIconComponent
                      name="Workflow"
                      className="h-3.5 w-3.5 shrink-0 text-destructive/60"
                    />
                    <span className="text-sm text-foreground">
                      {flow?.name ?? "Unknown flow"}
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
