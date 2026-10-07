import { useUpdateNodeInternals } from "@xyflow/react";
import { AnimatePresence, motion } from "framer-motion";
import { cloneDeep } from "lodash";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { processNodeAdvancedFields } from "@/CustomNodes/helpers/process-node-advanced-fields";
import useUpdateAllNodes, {
  type UpdateNodesType,
} from "@/CustomNodes/hooks/use-update-all-nodes";
import { Button } from "@/components/ui/button";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import UpdateComponentModal from "@/modals/updateComponentModal";
import useAlertStore from "@/stores/alertStore";
import useFlowStore, {
  completeNodeUpdate,
  registerNodeUpdate,
} from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { NodeDataType } from "@/types/flow";
import { cn } from "@/utils/utils";

const CONTAINER_VARIANTS = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 20 },
};

export default function UpdateAllComponents() {
  const { t } = useTranslation();
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
        title: t("errors.edgesLost"),
      });

      resetEdgesUpdateRef();
    }
  }, [edges]);

  const getSuccessTitle = (updatedCount: number) => {
    resetEdgesUpdateRef();
    return t("updateComponents.successCount", { count: updatedCount });
  };

  const breakingChanges = updatableComponents.filter(
    (component) => component.breakingChange,
  );

  const handleUpdateAllComponents = async (
    confirmed?: boolean,
    ids?: string[],
  ): Promise<void> => {
    if (updatableComponents.length === 0) {
      return;
    }
    if (!confirmed && breakingChanges.length > 0) {
      setIsOpen(true);
      return;
    }
    startEdgesUpdateRef();

    const nodesToUpdate = updatableComponents.filter(
      (component) => ids?.includes(component.id) ?? true,
    );
    const registeredNodeIds: string[] = [];
    let errorReported = false;
    setLoadingUpdate(true);

    try {
      takeSnapshot();

      // Register all pending updates so buildFlow will wait for them.
      for (const nodeUpdate of nodesToUpdate) {
        registerNodeUpdate(nodeUpdate.id);
        registeredNodeIds.push(nodeUpdate.id);
      }

      const updatePromises = nodesToUpdate.map(async (nodeUpdate) => {
        const node = nodes.find((n) => n.id === nodeUpdate.id);
        if (!node || node.type !== "genericNode") {
          throw new Error(`Unable to find updatable node ${nodeUpdate.id}`);
        }

        const thisNodeTemplate = templates[node.data.type]?.template;
        if (!thisNodeTemplate?.code) {
          throw new Error(`Unable to find template code for ${nodeUpdate.id}`);
        }

        const currentCode = thisNodeTemplate.code.value;
        const validation = await validateComponentCode({
          code: currentCode,
          frontend_node: node.data.node!,
        });
        if (!validation) return undefined;
        const { data: resData, type } = validation;

        if (!resData || !type) {
          throw new Error(`Validation returned no update for ${nodeUpdate.id}`);
        }

        return {
          nodeId: nodeUpdate.id,
          newNode: processNodeAdvancedFields(resData, edges, nodeUpdate.id),
          code: currentCode,
          name: "code",
          type,
        } satisfies UpdateNodesType;
      });

      const results = await Promise.allSettled(updatePromises);
      const updates = results.flatMap((result) =>
        result.status === "fulfilled" && result.value ? [result.value] : [],
      );
      const updatedNodeIds = updates.map(({ nodeId }) => nodeId);

      if (updatedNodeIds.length > 0) {
        updateAllNodes(updates);
        removeDismissedNodes(updatedNodeIds);
      }

      const failedCount = results.filter(
        (result) => result.status === "rejected",
      ).length;
      if (failedCount > 0) {
        resetEdgesUpdateRef();
        errorReported = true;
        setErrorData({
          title: t("errors.updateComponents"),
          list: [
            t("errors.updateComponentsList"),
            t("errors.updateComponentsContact"),
          ],
        });
        throw new Error(
          `Failed to update ${failedCount} of ${nodesToUpdate.length} components`,
        );
      }

      if (updatedNodeIds.length > 0) {
        useAlertStore.getState().setSuccessData({
          title: getSuccessTitle(updatedNodeIds.length),
        });
      }
    } catch (error) {
      resetEdgesUpdateRef();
      if (!errorReported) {
        setErrorData({
          title: t("errors.updateComponents"),
          list: [
            t("errors.updateComponentsList"),
            t("errors.updateComponentsContact"),
          ],
        });
      }
      throw error;
    } finally {
      for (const nodeId of registeredNodeIds) {
        completeNodeUpdate(nodeId);
      }
      setLoadingUpdate(false);
    }
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

  return (
    <AnimatePresence mode="wait">
      {!shouldHide && (
        <div className="absolute bottom-16 left-1/2 z-50 w-[530px] -translate-x-1/2">
          <motion.div
            initial="hidden"
            animate="visible"
            exit="exit"
            variants={CONTAINER_VARIANTS}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className={cn(
              "flex items-center justify-between gap-6 rounded-lg border bg-background px-4 py-3 text-sm shadow-md",
              (showDismissedWarning ||
                !allowCustomComponents ||
                updatableComponents.some(
                  (component) => component.breakingChange,
                )) &&
                "border-accent-amber-foreground",
            )}
          >
            <div className="flex flex-col gap-1">
              <span className="font-semibold">
                {showDismissedWarning
                  ? blockedComponents.length > 0
                    ? t("updateComponents.customComponentsDisabled")
                    : t("updateComponents.upgradeRequired")
                  : t("updateComponents.flowNeedsReview")}
              </span>
              {!showDismissedWarning && (
                <div className="flex flex-col font-normal text-muted-foreground">
                  {blockedComponents.length > 0 && (
                    <span>
                      {t("updateComponents.blockedCannotRun", {
                        count: blockedComponents.length,
                      })}
                    </span>
                  )}
                  {updatableComponents.length > 0 && (
                    <span>
                      {t("updateComponents.updatableCount", {
                        count: updatableComponents.length,
                      })}
                    </span>
                  )}
                </div>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-3">
              {!allDismissed && (
                <Button
                  variant="outline"
                  size="sm"
                  className="shrink-0"
                  onClick={handleDismissAllComponents}
                >
                  {componentsToUpdateFiltered.length > 1
                    ? t("updateComponents.dismissAll")
                    : t("updateComponents.dismiss")}
                </Button>
              )}
              {updatableComponents.length > 0 && (
                <Button
                  size="sm"
                  className="shrink-0"
                  onClick={() =>
                    void handleUpdateAllComponents().catch(() => undefined)
                  }
                  loading={loadingUpdate}
                  data-testid="update-all-button"
                >
                  {breakingChanges.length > 0
                    ? t("updateComponents.reviewAll")
                    : t("updateComponents.updateAll")}
                </Button>
              )}
            </div>
          </motion.div>
          <UpdateComponentModal
            isMultiple={true}
            open={isOpen}
            setOpen={setIsOpen}
            onUpdateNode={(ids) => handleUpdateAllComponents(true, ids)}
            components={updatableComponents}
          />
        </div>
      )}
    </AnimatePresence>
  );
}
