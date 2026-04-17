import { useCallback, useEffect, useRef } from "react";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import { useAttachFlowsData } from "../hooks/use-attach-flows-data";
import { useConnectionPanelState } from "../hooks/use-connection-panel-state";
import { useFlowAttachment } from "../hooks/use-flow-attachment";
import { ConnectionPanel } from "./step-attach-flows-connection-panel";
import { FlowListPanel } from "./step-attach-flows-flow-list-panel";
import { VersionPanel } from "./step-attach-flows-version-panel";

export default function StepAttachFlows() {
  const {
    isEditMode,
    initialFlowId,
    selectedInstance,
    connections,
    setConnections,
    selectedVersionByFlow,
    handleSelectVersion: onSelectVersion,
    toolNameByFlow,
    setToolNameByFlow,
    attachedConnectionByFlow,
    setAttachedConnectionByFlow: onAttachConnection,
    removedFlowIds,
    handleRemoveAttachedFlow,
    handleUndoRemoveFlow,
  } = useDeploymentStepper();

  const {
    selectedFlowId,
    rightPanel,
    setRightPanel,
    commitPendingAttachment,
    resetPendingAttachment,
    beginPendingAttachment,
    detectEnvVarsForVersion,
    handleDetachFlow,
    handleSelectFlow: selectFlow,
  } = useFlowAttachment({
    initialFlowId,
    onSelectVersion,
    setToolNameByFlow,
    handleRemoveAttachedFlow,
  });

  const {
    flows,
    effectiveFlowId,
    versions,
    isLoadingVersions,
    selectedFlow,
    globalVariableOptions,
  } = useAttachFlowsData({
    initialFlowId,
    selectedFlowId,
    selectedVersionByFlow,
    selectedInstanceId: selectedInstance?.id,
    setConnections,
  });

  const {
    connectionTab,
    setConnectionTab,
    selectedConnections,
    setSelectedConnections,
    newConnectionName,
    setNewConnectionName,
    envVars,
    detectedVarCount,
    isDuplicateConnectionName,
    handleAttachConnection,
    handleCreateConnection,
    handleSkipConnection,
    handleChangeFlow,
    handleAddEnvVar,
    handleEnvVarChange,
    handleEnvVarSelectGlobalVar,
    initConnectionsForFlow,
    updateDetectedEnvVars,
  } = useConnectionPanelState({
    connections,
    setConnections,
    effectiveFlowId,
    attachedConnectionByFlow,
    onAttachConnection,
    commitPendingAttachment,
    resetPendingAttachment,
    setRightPanel,
  });

  // When a flow+version are pre-selected from outside (e.g., canvas deploy button),
  // auto-advance to the connections panel and detect env vars for the pre-selected version.
  const initializedPreselectedFlow = useRef(false);
  useEffect(() => {
    if (initializedPreselectedFlow.current) {
      return;
    }
    const preSelected = initialFlowId
      ? selectedVersionByFlow.get(initialFlowId)
      : undefined;
    if (!preSelected) {
      return;
    }
    initializedPreselectedFlow.current = true;

    setRightPanel("connections");
    void detectEnvVarsForVersion(preSelected.versionId, updateDetectedEnvVars);
  }, [
    initialFlowId,
    selectedVersionByFlow,
    setRightPanel,
    detectEnvVarsForVersion,
    updateDetectedEnvVars,
  ]);

  const handleAttachFlow = useCallback(
    async (versionId: string) => {
      if (!effectiveFlowId) {
        return;
      }
      const version = versions.find((v) => v.id === versionId);
      beginPendingAttachment({
        flowId: effectiveFlowId,
        versionId,
        versionTag: version?.version_tag ?? "",
      });
      initConnectionsForFlow(effectiveFlowId);
      await detectEnvVarsForVersion(versionId, updateDetectedEnvVars);
    },
    [
      effectiveFlowId,
      versions,
      beginPendingAttachment,
      initConnectionsForFlow,
      detectEnvVarsForVersion,
      updateDetectedEnvVars,
    ],
  );

  const handleSelectFlow = useCallback(
    (flowId: string) => {
      selectFlow(flowId, () => setSelectedConnections(new Set()));
    },
    [selectFlow, setSelectedConnections],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 py-3">
      <h2 className="text-lg font-semibold">Attach Flows</h2>

      <div className="flex min-h-0 flex-1 overflow-hidden rounded-xl border border-border">
        <FlowListPanel
          flows={flows}
          selectedFlowId={effectiveFlowId}
          selectedVersionByFlow={selectedVersionByFlow}
          attachedConnectionByFlow={attachedConnectionByFlow}
          connections={connections}
          removedFlowIds={isEditMode ? removedFlowIds : undefined}
          onSelectFlow={handleSelectFlow}
          onRemoveFlow={handleDetachFlow}
          onUndoRemoveFlow={isEditMode ? handleUndoRemoveFlow : undefined}
        />

        {/* Right panel */}
        <div className="flex min-w-0 flex-1 flex-col">
          {rightPanel === "versions" ? (
            <VersionPanel
              selectedFlow={selectedFlow}
              versions={versions}
              isLoadingVersions={isLoadingVersions}
              selectedVersionByFlow={selectedVersionByFlow}
              onAttach={handleAttachFlow}
            />
          ) : (
            <ConnectionPanel
              connectionTab={connectionTab}
              onTabChange={setConnectionTab}
              connections={connections}
              selectedConnections={selectedConnections}
              onToggleConnection={(id) =>
                setSelectedConnections((prev) => {
                  const next = new Set(prev);
                  next.has(id) ? next.delete(id) : next.add(id);
                  return next;
                })
              }
              newConnectionName={newConnectionName}
              onNameChange={setNewConnectionName}
              envVars={envVars}
              detectedVarCount={detectedVarCount}
              globalVariableOptions={globalVariableOptions}
              onEnvVarChange={handleEnvVarChange}
              onEnvVarSelectGlobalVar={handleEnvVarSelectGlobalVar}
              onAddEnvVar={handleAddEnvVar}
              onChangeFlow={handleChangeFlow}
              onSkipConnection={handleSkipConnection}
              onAttachConnection={handleAttachConnection}
              onCreateConnection={handleCreateConnection}
              isDuplicateName={isDuplicateConnectionName}
            />
          )}
        </div>
      </div>
    </div>
  );
}
