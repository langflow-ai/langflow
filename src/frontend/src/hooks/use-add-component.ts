import { useStoreApi } from "@xyflow/react";
import { cloneDeep } from "lodash";
import { useCallback } from "react";
import { NODE_WIDTH } from "@/constants/constants";
import { track } from "@/customization/utils/analytics";
import { useCloudModeStore } from "@/stores/cloudModeStore";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import {
  applyCloudDefaultOverrides,
  getCloudUiMetadata,
  sanitizeCloudIncompatibleDefaults,
} from "@/utils/cloudMetadataUtils";
import { getNodeId } from "@/utils/reactflowUtils";
import { getNodeRenderType } from "@/utils/utils";

export function useAddComponent() {
  const store = useStoreApi();
  const paste = useFlowStore((state) => state.paste);
  const filterEdge = useFlowStore((state) => state.getFilterEdge);
  const filterType = useFlowStore((state) => state.filterType);
  const cloudOnly = useCloudModeStore((state) => state.cloudOnly);

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

      const outputType = filterType?.type;

      const outputToFilter = component.outputs?.find(
        (output) => outputType && output.types.includes(outputType),
      );

      const componentMetadata = getCloudUiMetadata(component.metadata);

      const cloudDefaultOverrides = componentMetadata?.cloud_default_overrides;
      const cloudIncompatibleOptions =
        componentMetadata?.cloud_incompatible_options;

      const componentNode =
        cloudOnly && (cloudDefaultOverrides || cloudIncompatibleOptions)
          ? (() => {
              const clonedComponent = cloneDeep(component);

              applyCloudDefaultOverrides(
                clonedComponent,
                cloudDefaultOverrides,
              );
              sanitizeCloudIncompatibleDefaults(
                clonedComponent,
                cloudIncompatibleOptions,
              );

              return clonedComponent;
            })()
          : component;

      const newNode: AllNodeType = {
        id: newId,
        type: getNodeRenderType("genericnode"),
        position: { x: 0, y: 0 },
        data: {
          node: componentNode,
          showNode: !componentNode.minimized,
          type: type,
          id: newId,
          ...(outputToFilter && { selected_output: outputToFilter.name }),
        },
      };

      paste({ nodes: [newNode], edges: [] }, pos);
    },
    [store, paste, filterType, cloudOnly],
  );

  return addComponent;
}
