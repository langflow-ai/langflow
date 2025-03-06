import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { processNodeAdvancedFields } from "@/CustomNodes/helpers/process-node-advanced-fields";
import useUpdateAllNodes, {
  UpdateNodesType,
} from "@/CustomNodes/hooks/use-update-all-nodes";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";
import { useUpdateNodeInternals } from "@xyflow/react";
import { useEffect, useMemo, useRef, useState } from "react";

const ERROR_MESSAGE_UPDATING_COMPONENTS = "Error updating components";
const ERROR_MESSAGE_UPDATING_COMPONENTS_LIST = [
  "There was an error updating the components.",
  "If the error persists, please report it on our Discord or GitHub.",
];
const ERROR_MESSAGE_EDGES_LOST =
  "Some edges were lost after updating the components. Please review the flow and reconnect them.";

export default function UpdateAllComponents({}: {}) {
  const { componentsToUpdate, nodes, edges, setNodes } = useFlowStore();
  const setDismissAll = useUtilityStore((state) => state.setDismissAll);
  const templates = useTypesStore((state) => state.templates);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync: validateComponentCode } = usePostValidateComponentCode();
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  const updateNodeInternals = useUpdateNodeInternals();
  const updateAllNodes = useUpdateAllNodes(setNodes, updateNodeInternals);

  const [loadingUpdate, setLoadingUpdate] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const edgesUpdateRef = useRef({
    numberOfEdgesBeforeUpdate: 0,
    updateComponent: false,
  });

  useMemo(() => {
    if (
      edgesUpdateRef.current.numberOfEdgesBeforeUpdate > 0 &&
      edges.length !== edgesUpdateRef.current.numberOfEdgesBeforeUpdate &&
      edgesUpdateRef.current.updateComponent
    ) {
      useAlertStore.getState().setNoticeData({
        title: ERROR_MESSAGE_EDGES_LOST,
      });

      resetEdgesUpdateRef();
    }
  }, [edges]);

  const getSuccessTitle = (updatedCount: number) => {
    resetEdgesUpdateRef();
    return `Successfully updated ${updatedCount} component${
      updatedCount > 1 ? "s" : ""
    }`;
  };

  const handleUpdateAllComponents = () => {
    startEdgesUpdateRef();

    setLoadingUpdate(true);
    takeSnapshot();

    let updatedCount = 0;
    const updates: UpdateNodesType[] = [];

    const updatePromises = componentsToUpdate.map((nodeId) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (!node || node.type !== "genericNode") return Promise.resolve();

      const thisNodeTemplate = templates[node.data.type]?.template;
      if (!thisNodeTemplate?.code) return Promise.resolve();

      const currentCode = thisNodeTemplate.code.value;

      return new Promise((resolve) => {
        validateComponentCode({
          code: currentCode,
          frontend_node: node.data.node!,
        })
          .then(({ data: resData, type }) => {
            if (resData && type) {
              const newNode = processNodeAdvancedFields(resData, edges, nodeId);

              updates.push({
                nodeId,
                newNode,
                code: currentCode,
                name: "code",
                type,
              });

              updatedCount++;
            }
            resolve(null);
          })
          .catch((error) => {
            console.error(error);
            resolve(null);
          });
      });
    });

    Promise.all(updatePromises)
      .then(() => {
        if (updatedCount > 0) {
          updateAllNodes(updates);

          useAlertStore.getState().setSuccessData({
            title: getSuccessTitle(updatedCount),
          });
        }
      })
      .catch((error) => {
        setErrorData({
          title: ERROR_MESSAGE_UPDATING_COMPONENTS,
          list: ERROR_MESSAGE_UPDATING_COMPONENTS_LIST,
        });
        console.error(error);
      })
      .finally(() => {
        setLoadingUpdate(false);
      });
  };

  const resetEdgesUpdateRef = () => {
    edgesUpdateRef.current = {
      numberOfEdgesBeforeUpdate: 0,
      updateComponent: false,
    };
  };

  const startEdgesUpdateRef = () => {
    edgesUpdateRef.current = {
      numberOfEdgesBeforeUpdate: edges.length,
      updateComponent: true,
    };
  };

  if (componentsToUpdate.length === 0) return null;

  return (
    <div
      className={cn(
        "absolute bottom-2 left-1/2 z-50 flex w-[500px] -translate-x-1/2 items-center gap-8 rounded-lg bg-warning px-4 py-2 text-sm font-medium text-warning-foreground shadow-md transition-all ease-in",
        dismissed && "translate-y-[120%]",
      )}
    >
      <div className="flex items-center gap-3">
        <ForwardedIconComponent
          name="AlertTriangle"
          className="!h-[18px] !w-[18px] shrink-0"
          strokeWidth={1.5}
        />
        <span>
          {componentsToUpdate.length} component
          {componentsToUpdate.length > 1 ? "s are" : " is"} ready to update
        </span>
      </div>
      <div className="flex items-center gap-4">
        <Button
          variant="link"
          size="icon"
          className="shrink-0 text-sm text-warning-foreground"
          onClick={(e) => {
            setDismissed(true);
            setDismissAll(true);
            e.stopPropagation();
          }}
        >
          Dismiss
        </Button>
        <Button
          variant="warning"
          size="sm"
          className="shrink-0"
          onClick={handleUpdateAllComponents}
          loading={loadingUpdate}
          data-testid="update-all-button"
        >
          Update All
        </Button>
      </div>
    </div>
  );
}
