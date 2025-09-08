import { useStoreApi } from "@xyflow/react";
import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import { NODE_WIDTH } from "@/constants/constants";
import { track } from "@/customization/utils/analytics";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import { getNodeId } from "@/utils/reactflowUtils";
import { getNodeRenderType } from "@/utils/utils";
import { useUtilityStore } from "@/stores/utilityStore";

export function useAddComponent() {
  const store = useStoreApi();
  const {
    paste,
    setFilterEdge,
    setFilterType,
    setFilterComponent,
    setHandleDragging,
  } = useFlowStore(
    useShallow((state) => ({
      paste: state.paste,
      setFilterEdge: state.setFilterEdge,
      setFilterType: state.setFilterType,
      setFilterComponent: state.setFilterComponent,
      setHandleDragging: state.setHandleDragging,
    }))
  );
  const isAwaitingInputAgentModel = useUtilityStore(
    (state) => state.awaitInputAgentModel
  );
  const setAwaitInputAgentModel = useUtilityStore(
    (state) => state.setAwaitInputAgentModel
  );

  const addComponent = useCallback(
    (
      component: APIClassType,
      type: string,
      position?: { x: number; y: number }
    ) => {
      track("Component Added", { componentType: component.display_name });

      let selectedOutput = "";

      const {
        height,
        width,
        transform: [transformX, transformY, zoomLevel],
      } = store.getState();

      const zoomMultiplier = 1 / zoomLevel;

      let pos;

      if (position) {
        pos = position;
      } else {
        let centerX, centerY;

        centerX = -transformX * zoomMultiplier + (width * zoomMultiplier) / 2;
        centerY = -transformY * zoomMultiplier + (height * zoomMultiplier) / 2;

        const nodeOffset = NODE_WIDTH / 2;

        pos = {
          x: -nodeOffset,
          y: -nodeOffset,
          paneX: centerX,
          paneY: centerY,
        };
      }

      if (isAwaitingInputAgentModel) {
        component.outputs?.forEach((output) => {
          if (output.types.includes("LanguageModel")) {
            selectedOutput = output.name;
            setAwaitInputAgentModel(false);

            // Reset all filters when successfully adding a LanguageModel component
            setFilterEdge([]);
            setFilterType(undefined);
            setFilterComponent("");
            setHandleDragging(undefined);
          }
        });
      }

      const newId = getNodeId(type);

      const newNode: AllNodeType = {
        id: newId,
        type: getNodeRenderType("genericnode"),
        position: { x: 0, y: 0 },
        data: {
          node: component,
          showNode: !component.minimized,
          type: type,
          id: newId,
          ...(selectedOutput ? { selected_output: selectedOutput } : {}),
        },
      };

      paste({ nodes: [newNode], edges: [] }, pos);
    },
    [
      store,
      paste,
      setFilterEdge,
      setFilterType,
      setFilterComponent,
      setHandleDragging,
      isAwaitingInputAgentModel,
      setAwaitInputAgentModel,
    ]
  );

  return addComponent;
}
