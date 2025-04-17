import { NODE_WIDTH } from "@/constants/constants";
import { track } from "@/customization/utils/analytics";
import useFlowStore from "@/stores/flowStore";
import { APIClassType } from "@/types/api";
import { AllNodeType } from "@/types/flow";
import { getNodeId } from "@/utils/reactflowUtils";
import { getNodeRenderType } from "@/utils/utils";
import { useStoreApi } from "@xyflow/react";
import { useCallback } from "react";

export function useAddComponent() {
  const store = useStoreApi();
  const paste = useFlowStore((state) => state.paste);

  const addComponent = useCallback(
    (
      component: APIClassType,
      type: string,
      position?: { x: number; y: number },
    ) => {
      track("Component Added", { componentType: component.display_name });

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
        },
      };

      paste({ nodes: [newNode], edges: [] }, pos);
    },
    [store, paste],
  );

  return addComponent;
}
