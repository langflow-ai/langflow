import { useCallback, useMemo, useState } from "react";
import type {
  DeploymentStepperInitialState,
  FlowVersionSelection,
} from "../contexts/deployment-stepper.types";

export function useDeploymentEditSession(
  initialState?: DeploymentStepperInitialState,
) {
  const [selectedVersionByFlow, setSelectedVersionByFlow] = useState<
    Map<string, FlowVersionSelection>
  >(initialState?.selectedVersionByFlow ?? new Map());
  const [toolNameByFlow, setToolNameByFlow] = useState<Map<string, string>>(
    initialState?.initialToolNameByFlow ?? new Map(),
  );
  const [attachedConnectionByFlow, setAttachedConnectionByFlow] = useState<
    Map<string, string[]>
  >(initialState?.initialConnectionsByFlow ?? new Map());
  const [removedFlowIds, setRemovedFlowIds] = useState<Set<string>>(new Set());

  const initialVersionByFlow = useMemo(
    () =>
      initialState?.selectedVersionByFlow ??
      new Map<string, FlowVersionSelection>(),
    [],
  );
  const initialToolNameByFlow = useMemo(
    () => initialState?.initialToolNameByFlow ?? new Map<string, string>(),
    [],
  );
  const initialConnectionsByFlow = useMemo(
    () => initialState?.initialConnectionsByFlow ?? new Map<string, string[]>(),
    [],
  );
  const preExistingFlowIds = useMemo(
    () => new Set(initialVersionByFlow.keys()),
    [initialVersionByFlow],
  );

  const handleSelectVersion = useCallback(
    (flowId: string, versionId: string, versionTag: string) => {
      setSelectedVersionByFlow((prev) => {
        const next = new Map(prev);
        next.set(flowId, { versionId, versionTag });
        return next;
      });
    },
    [],
  );

  const handleRemoveAttachedFlow = useCallback((flowId: string) => {
    setRemovedFlowIds((prev) => new Set([...Array.from(prev), flowId]));
    setSelectedVersionByFlow((prev) => {
      const next = new Map(prev);
      next.delete(flowId);
      return next;
    });
    setAttachedConnectionByFlow((prev) => {
      const next = new Map(prev);
      next.delete(flowId);
      return next;
    });
  }, []);

  const handleUndoRemoveFlow = useCallback(
    (flowId: string) => {
      setRemovedFlowIds((prev) => {
        const next = new Set(prev);
        next.delete(flowId);
        return next;
      });

      const originalVersion = initialVersionByFlow.get(flowId);
      if (originalVersion) {
        setSelectedVersionByFlow((prev) => {
          const next = new Map(prev);
          next.set(flowId, originalVersion);
          return next;
        });
      }

      const originalConnections = initialConnectionsByFlow.get(flowId);
      if (originalConnections) {
        setAttachedConnectionByFlow((prev) => {
          const next = new Map(prev);
          next.set(flowId, originalConnections);
          return next;
        });
      }
    },
    [initialConnectionsByFlow, initialVersionByFlow],
  );

  return {
    selectedVersionByFlow,
    toolNameByFlow,
    attachedConnectionByFlow,
    removedFlowIds,
    initialVersionByFlow,
    initialToolNameByFlow,
    initialConnectionsByFlow,
    preExistingFlowIds,
    setToolNameByFlow,
    setAttachedConnectionByFlow,
    handleSelectVersion,
    handleRemoveAttachedFlow,
    handleUndoRemoveFlow,
  };
}
