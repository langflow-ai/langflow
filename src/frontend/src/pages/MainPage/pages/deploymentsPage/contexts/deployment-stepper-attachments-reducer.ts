import type { Dispatch, SetStateAction } from "react";

type FlowVersionEntry = {
  versionId: string;
  versionTag: string;
};

export interface DeploymentStepperAttachmentsState {
  selectedVersionByFlow: Map<string, FlowVersionEntry>;
  attachedConnectionByFlow: Map<string, string[]>;
  removedFlowIds: Set<string>;
}

type DeploymentStepperAttachmentsAction =
  | {
      type: "selectVersion";
      flowId: string;
      versionId: string;
      versionTag: string;
    }
  | {
      type: "setAttachedConnectionByFlow";
      value: SetStateAction<Map<string, string[]>>;
    }
  | {
      type: "removeAttachedFlow";
      flowId: string;
    }
  | {
      type: "undoRemoveFlow";
      flowId: string;
      initialVersionByFlow: Map<string, FlowVersionEntry>;
      initialConnectionsByFlow: Map<string, string[]>;
    };

export function createDeploymentStepperAttachmentsState(args?: {
  selectedVersionByFlow?: Map<string, FlowVersionEntry>;
  initialConnectionsByFlow?: Map<string, string[]>;
}): DeploymentStepperAttachmentsState {
  return {
    selectedVersionByFlow: args?.selectedVersionByFlow ?? new Map(),
    attachedConnectionByFlow: args?.initialConnectionsByFlow ?? new Map(),
    removedFlowIds: new Set(),
  };
}

export function deploymentStepperAttachmentsReducer(
  state: DeploymentStepperAttachmentsState,
  action: DeploymentStepperAttachmentsAction,
): DeploymentStepperAttachmentsState {
  switch (action.type) {
    case "selectVersion": {
      const selectedVersionByFlow = new Map(state.selectedVersionByFlow);
      selectedVersionByFlow.set(action.flowId, {
        versionId: action.versionId,
        versionTag: action.versionTag,
      });

      return {
        ...state,
        selectedVersionByFlow,
      };
    }
    case "setAttachedConnectionByFlow": {
      const attachedConnectionByFlow =
        typeof action.value === "function"
          ? action.value(state.attachedConnectionByFlow)
          : action.value;

      return {
        ...state,
        attachedConnectionByFlow,
      };
    }
    case "removeAttachedFlow": {
      const removedFlowIds = new Set(state.removedFlowIds);
      removedFlowIds.add(action.flowId);

      const selectedVersionByFlow = new Map(state.selectedVersionByFlow);
      selectedVersionByFlow.delete(action.flowId);

      const attachedConnectionByFlow = new Map(state.attachedConnectionByFlow);
      attachedConnectionByFlow.delete(action.flowId);

      return {
        selectedVersionByFlow,
        attachedConnectionByFlow,
        removedFlowIds,
      };
    }
    case "undoRemoveFlow": {
      const removedFlowIds = new Set(state.removedFlowIds);
      removedFlowIds.delete(action.flowId);

      const selectedVersionByFlow = new Map(state.selectedVersionByFlow);
      const originalVersion = action.initialVersionByFlow.get(action.flowId);
      if (originalVersion) {
        selectedVersionByFlow.set(action.flowId, originalVersion);
      }

      const attachedConnectionByFlow = new Map(state.attachedConnectionByFlow);
      const originalConnections = action.initialConnectionsByFlow.get(
        action.flowId,
      );
      if (originalConnections) {
        attachedConnectionByFlow.set(action.flowId, originalConnections);
      }

      return {
        selectedVersionByFlow,
        attachedConnectionByFlow,
        removedFlowIds,
      };
    }
  }
}

export function createSetAttachedConnectionByFlowDispatch(
  dispatch: Dispatch<DeploymentStepperAttachmentsAction>,
): Dispatch<SetStateAction<Map<string, string[]>>> {
  return (value) =>
    dispatch({
      type: "setAttachedConnectionByFlow",
      value,
    });
}
