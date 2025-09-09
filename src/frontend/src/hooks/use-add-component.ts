import { useStoreApi } from "@xyflow/react";
import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import { NODE_WIDTH } from "@/constants/constants";
import { track } from "@/customization/utils/analytics";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { APIClassType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import { getNodeId } from "@/utils/reactflowUtils";
import { getNodeRenderType } from "@/utils/utils";

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
    })),
  );
  const awaitConnectionConfig = useUtilityStore(
    (state) => state.awaitConnectionConfig,
  );
  const setAwaitConnectionConfig = useUtilityStore(
    (state) => state.setAwaitConnectionConfig,
  );

  const addComponent = useCallback(
    (
      component: APIClassType,
      type: string,
      position?: { x: number; y: number },
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

      if (awaitConnectionConfig) {
        component.outputs?.forEach((output) => {
          // Generic type matching instead of hardcoded LanguageModel check
          const hasMatchingType = awaitConnectionConfig.targetTypes.some(
            (targetType) => output.types.includes(targetType),
          );

          if (hasMatchingType) {
            selectedOutput = output.name;
            setAwaitConnectionConfig(null); // Clear generic state

            // Reset all filters when successfully adding a matching component
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
      awaitConnectionConfig,
      setAwaitConnectionConfig,
    ],
  );

  return addComponent;
}
