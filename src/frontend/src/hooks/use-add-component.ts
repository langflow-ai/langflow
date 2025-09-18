import { useStoreApi } from "@xyflow/react";
import { useCallback } from "react";
import { NODE_WIDTH } from "@/constants/constants";
import { track } from "@/customization/utils/analytics";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import { assignAliasToNewComponent } from "@/utils/aliasUtils";
import { getNodeId } from "@/utils/reactflowUtils";
import { getNodeRenderType } from "@/utils/utils";

export function useAddComponent() {
  const store = useStoreApi();
  const paste = useFlowStore((state) => state.paste);
  const nodes = useFlowStore((state) => state.nodes);
  const setNodes = useFlowStore((state) => state.setNodes);

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
          node: { ...component }, // Clone component to avoid mutation
          showNode: !component.minimized,
          type: type,
          id: newId,
        },
      };

      // Generate alias for the new component and update existing ones if needed
      assignAliasToNewComponent(newNode, nodes);

      // Check if we need to update existing nodes (when adding second component of same type)
      const displayName = newNode.data.node.display_name;
      const sameTypeNodes = nodes.filter(
        (n) =>
          n.type === "genericNode" && n.data.node.display_name === displayName,
      );

      if (sameTypeNodes.length === 1 && !sameTypeNodes[0].data.node.alias) {
        // This is the second component - need to assign aliases to both
        const firstNode = sameTypeNodes[0];
        if (firstNode.type === "genericNode") {
          firstNode.data.node.alias = `${displayName}#1`;
        }

        // Update the first node in the store
        setNodes((currentNodes) =>
          currentNodes.map((n) => (n.id === firstNode.id ? firstNode : n)),
        );
      }

      paste({ nodes: [newNode], edges: [] }, pos);
    },
    [store, paste, nodes, setNodes],
  );

  return addComponent;
}
