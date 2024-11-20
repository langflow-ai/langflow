import { ForwardedIconComponent } from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { usePostValidateComponentCode } from "@/controllers/API/queries/nodes/use-post-validate-component-code";
import { processNodeAdvancedFields } from "@/CustomNodes/helpers/process-node-advanced-fields";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import { cn } from "@/utils/utils";
import { useState } from "react";

export default function UpdateAllComponents() {
  const { componentsToUpdate, nodes, edges, setNode } = useFlowStore();
  const templates = useTypesStore((state) => state.templates);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [loadingUpdate, setLoadingUpdate] = useState(false);

  const { mutate: validateComponentCode } = usePostValidateComponentCode();

  const handleUpdateAllComponents = () => {
    setLoadingUpdate(true);
    let updatedCount = 0;

    const updatePromises = componentsToUpdate.map((nodeId) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return Promise.resolve();

      const thisNodeTemplate = templates[node.data.type]?.template;
      if (!thisNodeTemplate?.code) return Promise.resolve();

      const currentCode = thisNodeTemplate.code.value;

      return new Promise((resolve) => {
        validateComponentCode(
          { code: currentCode, frontend_node: node.data.node },
          {
            onSuccess: ({ data: resData, type }) => {
              if (resData && type) {
                const newNode = processNodeAdvancedFields(
                  resData,
                  edges,
                  nodeId,
                );
                setNode(nodeId, (oldNode) => ({
                  ...oldNode,
                  data: {
                    ...oldNode.data,
                    node: newNode,
                  },
                }));
                updatedCount++;
              }
              resolve(null);
            },
            onError: (error) => {
              console.error(error);
              resolve(null);
            },
          },
        );
      });
    });

    Promise.all(updatePromises)
      .then(() => {
        if (updatedCount > 0) {
          useAlertStore.getState().setSuccessData({
            title: `Successfully updated ${updatedCount} component${
              updatedCount > 1 ? "s" : ""
            }`,
          });
        }
      })
      .catch((error) => {
        setErrorData({
          title: "Error updating components",
          list: [
            "There was an error updating the components.",
            "If the error persists, please report it on our Discord or GitHub.",
          ],
        });
        console.error(error);
      })
      .finally(() => {
        setLoadingUpdate(false);
      });
  };

  if (componentsToUpdate.length === 0) return null;

  return (
    <div
      className={cn(
        "text-warning-foreground bg-warning absolute bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium shadow-md",
      )}
    >
      <ForwardedIconComponent
        name="AlertTriangle"
        className="h-4 w-4"
        strokeWidth={1.5}
      />
      <span>
        {componentsToUpdate.length} component
        {componentsToUpdate.length > 1 ? "s" : ""} can be updated
      </span>
      <Button
        variant="warning"
        size="sm"
        className="ml-2 h-7 px-2 text-xs"
        onClick={handleUpdateAllComponents}
        loading={loadingUpdate}
      >
        Update All
      </Button>
    </div>
  );
}
