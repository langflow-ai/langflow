import { useUpdateNodeInternals } from "@xyflow/react";
import { cloneDeep } from "lodash";
import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useRef, useState } from "react";
import { processNodeAdvancedFields } from "@/CustomNodes/helpers/process-node-advanced-fields";
import useUpdateAllNodes, {
  type UpdateNodesType,
} from "@/CustomNodes/hooks/use-update-all-nodes";
import { Button } from "@/components/ui/button";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import UpdateComponentModal from "@/modals/updateComponentModal";
import useAlertStore from "@/stores/alertStore";
import useFlowStore, {
  registerNodeUpdate,
  completeNodeUpdate,
} from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { NodeDataType } from "@/types/flow";
import { cn } from "@/utils/utils";

const ERROR_MESSAGE_UPDATING_COMPONENTS = "Error updating components";
const ERROR_MESSAGE_UPDATING_COMPONENTS_LIST = [
  "There was an error updating the components.",
  "If the error persists, please report it on our Discord or GitHub.",
];
const ERROR_MESSAGE_EDGES_LOST =
  "Some edges were lost after updating the components. Please review the flow and reconnect them.";

const CONTAINER_VARIANTS = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 20 },
};

export default function UpdateAllComponents() {
  const { componentsToUpdate, nodes, edges, setNodes } = useFlowStore();
  const templates = useTypesStore((state) => state.templates);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync: validateComponentCode } = usePostValidateComponentCode();
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  const isBuilding = useFlowStore((state) => state.isBuilding);
  const buildInfo = useFlowStore((state) => state.buildInfo);

  const updateNodeInternals = useUpdateNodeInternals();
  const updateAllNodes = useUpdateAllNodes(setNodes, updateNodeInternals);

  const [loadingUpdate, setLoadingUpdate] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const dismissedNodes = useFlowStore((state) => state.dismissedNodes);
  const addDismissedNodes = useFlowStore((state) => state.addDismissedNodes);
  const removeDismissedNodes = useFlowStore(
    (state) => state.removeDismissedNodes,
  );
  const allowCustomComponents = useUtilityStore(
    (state) => state.allowCustomComponents,
  );

  const allDismissed = useMemo(
    () =>
      componentsToUpdate.length > 0 &&
      componentsToUpdate.every((component) =>
        dismissedNodes.includes(component.id),
      ),
    [dismissedNodes, componentsToUpdate],
  );

  const componentsToUpdateFiltered = useMemo(
    () =>
      allowCustomComponents
        ? componentsToUpdate.filter(
            (component) =>
              !component.blocked &&
              !dismissedNodes.includes(component.id) &&
              !component.userEdited,
          )
        : componentsToUpdate,
    [componentsToUpdate, dismissedNodes, allowCustomComponents],
  );

  const blockedComponents = useMemo(
    () => componentsToUpdateFiltered.filter((component) => component.blocked),
    [componentsToUpdateFiltered],
  );

  const updatableComponents = useMemo(
    () => componentsToUpdateFiltered.filter((component) => !component.blocked),
    [componentsToUpdateFiltered],
  );

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

  const breakingChanges = updatableComponents.filter(
    (component) => component.breakingChange,
  );

  const handleUpdateAllComponents = (confirmed?: boolean, ids?: string[]) => {
    if (updatableComponents.length === 0) {
      return;
    }
    if (!confirmed && breakingChanges.length > 0) {
      setIsOpen(true);
      return;
    }
    startEdgesUpdateRef();

    setLoadingUpdate(true);
    takeSnapshot();

    let updatedCount = 0;
    const updates: UpdateNodesType[] = [];

    const nodesToUpdate = updatableComponents.filter(
      (component) => ids?.includes(component.id) ?? true,
    );

    // Register all pending updates so buildFlow will wait for them
    for (const nodeUpdate of nodesToUpdate) {
      registerNodeUpdate(nodeUpdate.id);
    }

    const updatePromises = nodesToUpdate.map((nodeUpdate) => {
      const node = nodes.find((n) => n.id === nodeUpdate.id);
      if (!node || node.type !== "genericNode") {
        completeNodeUpdate(nodeUpdate.id);
        return Promise.resolve();
      }

      const thisNodeTemplate = templates[node.data.type]?.template;
      if (!thisNodeTemplate?.code) {
        completeNodeUpdate(nodeUpdate.id);
        return Promise.resolve();
      }

      const currentCode = thisNodeTemplate.code.value;

      return new Promise((resolve) => {
        validateComponentCode({
          code: currentCode,
          frontend_node: node.data.node!,
        })
          .then(({ data: resData, type }) => {
            if (resData && type) {
              const newNode = processNodeAdvancedFields(
                resData,
                edges,
                nodeUpdate.id,
              );

              updates.push({
                nodeId: nodeUpdate.id,
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
        const updatedNodeIds = updates.map(({ nodeId }) => nodeId);

        if (updatedNodeIds.length > 0) {
          updateAllNodes(updates);
          removeDismissedNodes(updatedNodeIds);

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
        // Complete all pending updates regardless of success/failure
        for (const nodeUpdate of nodesToUpdate) {
          completeNodeUpdate(nodeUpdate.id);
        }
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

  const handleDismissAllComponents = (
    e: React.MouseEvent<HTMLButtonElement>,
  ) => {
    const ids = componentsToUpdateFiltered.map((component) => component.id);
    addDismissedNodes(ids);
    setNodes((oldNodes) =>
      oldNodes.map((node) => {
        if (ids.includes(node.id) && node.data?.node) {
          const newNode = cloneDeep(node);
          (newNode.data as NodeDataType).node!.edited = true;
          return newNode;
        }
        return node;
      }),
    );
    e.stopPropagation();
  };

  if (componentsToUpdateFiltered.length === 0) return null;

  const shouldHide =
    (allowCustomComponents && allDismissed) ||
    isBuilding ||
    buildInfo?.error ||
    buildInfo?.success;

  const showDismissedWarning = !allowCustomComponents && allDismissed;
  const summaryMessage = showDismissedWarning
    ? blockedComponents.length > 0
      ? "Custom components are disabled"
      : "Upgrade is required to execute flow"
    : !allowCustomComponents
      ? blockedComponents.length > 0 && updatableComponents.length > 0
        ? `${blockedComponents.length} custom component${blockedComponents.length > 1 ? "s cannot" : " cannot"} run and ${updatableComponents.length} component${updatableComponents.length > 1 ? "s must" : " must"} be updated before this flow can run`
        : blockedComponents.length > 0
          ? `${blockedComponents.length} custom component${blockedComponents.length > 1 ? "s cannot" : " cannot"} run while custom components are disabled`
          : `${updatableComponents.length} component${updatableComponents.length > 1 ? "s must" : " must"} be updated before this flow can run`
      : `Update${updatableComponents.length > 1 ? "s are" : " is"} available for ${updatableComponents.length} component${updatableComponents.length > 1 ? "s" : ""}`;

  return (
    <AnimatePresence mode="wait">
      {!shouldHide && (
        <div className="absolute bottom-2 left-1/2 z-50 w-[530px] -translate-x-1/2">
          <motion.div
            initial="hidden"
            animate="visible"
            exit="exit"
            variants={CONTAINER_VARIANTS}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className={cn(
              "flex items-center justify-between gap-8 rounded-lg border bg-background px-4 py-2 text-sm font-medium shadow-md",
              (showDismissedWarning ||
                !allowCustomComponents ||
                updatableComponents.some(
                  (component) => component.breakingChange,
                )) &&
                "border-accent-amber-foreground",
            )}
          >
            <div className="flex items-center gap-3">
              <span>{summaryMessage}</span>
            </div>
            <div className="flex items-center gap-4">
              {!allDismissed && (
                <Button
                  variant="link"
                  size="icon"
                  className="shrink-0 text-sm"
                  onClick={handleDismissAllComponents}
                >
                  Dismiss {componentsToUpdateFiltered.length > 1 ? "All" : ""}
                </Button>
              )}
              {updatableComponents.length > 0 && (
                <Button
                  size="sm"
                  className="shrink-0"
                  onClick={() => handleUpdateAllComponents()}
                  loading={loadingUpdate}
                  data-testid="update-all-button"
                >
                  {breakingChanges.length > 0 ? "Review All" : "Update All"}
                </Button>
              )}
            </div>
            <UpdateComponentModal
              isMultiple={true}
              open={isOpen}
              setOpen={setIsOpen}
              onUpdateNode={(ids) => handleUpdateAllComponents(true, ids)}
              components={updatableComponents}
            />
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
