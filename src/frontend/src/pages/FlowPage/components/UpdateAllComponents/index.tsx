import { processNodeAdvancedFields } from "@/CustomNodes/helpers/process-node-advanced-fields";
import useUpdateAllNodes, {
  type UpdateNodesType,
} from "@/CustomNodes/hooks/use-update-all-nodes";
import { Button } from "@/components/ui/button";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import UpdateComponentModal from "@/modals/updateComponentModal";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import { cn } from "@/utils/utils";
import { useUpdateNodeInternals } from "@xyflow/react";
import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useRef, useState } from "react";

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

export default function UpdateAllComponents({}: {}) {
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

  const dismissed = useMemo(
    () =>
      componentsToUpdate.every((component) =>
        dismissedNodes.includes(component.id),
      ),
    [dismissedNodes, componentsToUpdate],
  );

  const componentsToUpdateFiltered = useMemo(
    () =>
      componentsToUpdate.filter(
        (component) =>
          !dismissedNodes.includes(component.id) && !component.userEdited,
      ),
    [componentsToUpdate, dismissedNodes],
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

  const breakingChanges = componentsToUpdateFiltered.filter(
    (component) => component.breakingChange,
  );

  const handleUpdateAllComponents = (confirmed?: boolean, ids?: string[]) => {
    if (!confirmed && breakingChanges.length > 0) {
      setIsOpen(true);
      return;
    }
    startEdgesUpdateRef();

    setLoadingUpdate(true);
    takeSnapshot();

    let updatedCount = 0;
    const updates: UpdateNodesType[] = [];

    const updatePromises = componentsToUpdateFiltered
      .filter((component) => ids?.includes(component.id) ?? true)
      .map((nodeUpdate) => {
        const node = nodes.find((n) => n.id === nodeUpdate.id);
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

  const handleDismissAllComponents = (
    e: React.MouseEvent<HTMLButtonElement>,
  ) => {
    addDismissedNodes(
      componentsToUpdateFiltered.map((component) => component.id),
    );
    e.stopPropagation();
  };

  if (componentsToUpdateFiltered.length === 0) return null;

  return (
    <AnimatePresence mode="wait">
      {!dismissed &&
        !isBuilding &&
        !buildInfo?.error &&
        !buildInfo?.success && (
          <div className="absolute bottom-2 left-1/2 z-50 w-[530px] -translate-x-1/2">
            <motion.div
              initial="hidden"
              animate="visible"
              exit="exit"
              variants={CONTAINER_VARIANTS}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className={cn(
                "flex items-center justify-between gap-8 rounded-lg border bg-background px-4 py-2 text-sm font-medium shadow-md",
                componentsToUpdateFiltered.some(
                  (component) => component.breakingChange,
                ) && "border-accent-amber-foreground",
              )}
            >
              <div className="flex items-center gap-3">
                <span>
                  Update
                  {componentsToUpdateFiltered.length > 1 ? "s are" : " is"}{" "}
                  available for{" "}
                  {componentsToUpdateFiltered.length +
                    " component" +
                    (componentsToUpdateFiltered.length > 1 ? "s" : "")}
                </span>
              </div>
              <div className="flex items-center gap-4">
                <Button
                  variant="link"
                  size="icon"
                  className="shrink-0 text-sm"
                  onClick={handleDismissAllComponents}
                >
                  Dismiss {componentsToUpdateFiltered.length > 1 ? "All" : ""}
                </Button>
                <Button
                  size="sm"
                  className="shrink-0"
                  onClick={() => handleUpdateAllComponents()}
                  loading={loadingUpdate}
                  data-testid="update-all-button"
                >
                  {breakingChanges.length > 0 ? "Review All" : "Update All"}
                </Button>
              </div>
              <UpdateComponentModal
                isMultiple={true}
                open={isOpen}
                setOpen={setIsOpen}
                onUpdateNode={(ids) => handleUpdateAllComponents(true, ids)}
                components={componentsToUpdateFiltered}
              />
            </motion.div>
          </div>
        )}
    </AnimatePresence>
  );
}
