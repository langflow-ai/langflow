import { usePostTemplateValue } from "@/controllers/API/queries/nodes/use-post-template-value";
import { track } from "@/customization/utils/analytics";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { APIClassType, InputFieldType } from "@/types/api";
import { NodeType } from "@/types/flow";
import { cloneDeep } from "lodash";
import { useUpdateNodeInternals } from "reactflow";
import { mutateTemplate } from "../helpers/mutate-template";

export type handleOnNewValueType = (
  changes: Partial<InputFieldType>,
  options?: {
    skipSnapshot?: boolean;
    setNodeClass?: (node: APIClassType) => void;
  },
) => void;

const useHandleOnNewValue = ({
  node,
  nodeId,
  name,
  setNode: setNodeExternal,
}: {
  node: APIClassType;
  nodeId: string;
  name: string;
  setNode?: (
    id: string,
    update: NodeType | ((oldState: NodeType) => NodeType),
  ) => void;
}) => {
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);

  const setNode = setNodeExternal ?? useFlowStore((state) => state.setNode);
  const updateNodeInternals = useUpdateNodeInternals();

  const setErrorData = useAlertStore((state) => state.setErrorData);
  const postTemplateValue = usePostTemplateValue({
    parameterId: name,
    nodeId: nodeId,
    node: node,
    tool_mode: node.tool_mode ?? false,
  });

  const handleOnNewValue: handleOnNewValueType = async (changes, options?) => {
    const newNode = cloneDeep(node);
    const template = newNode.template;

    track("Component Edited", { nodeId });

    if (!template) {
      setErrorData({ title: "Template not found in the component" });
      return;
    }

    const parameter = template[name];

    if (!parameter) {
      setErrorData({ title: "Parameter not found in the template" });
      return;
    }

    if (!options?.skipSnapshot) takeSnapshot();

    Object.entries(changes).forEach(([key, value]) => {
      if (value !== undefined) parameter[key] = value;
    });

    const shouldUpdate = parameter.real_time_refresh;

    const setNodeClass = (newNodeClass: APIClassType) => {
      options?.setNodeClass && options.setNodeClass(newNodeClass);
      setNode(
        nodeId,
        (oldNode) => {
          const newData = cloneDeep(oldNode.data);
          newData.node = newNodeClass;
          return {
            ...oldNode,
            data: newData,
          };
        },
        true,
        () => {
          updateNodeInternals(nodeId);
        },
      );
    };

    if (shouldUpdate && changes.value !== undefined) {
      mutateTemplate(
        changes.value,
        newNode,
        setNodeClass,
        postTemplateValue,
        setErrorData,
      );
    }

    setNode(
      nodeId,
      (oldNode) => {
        const newData = cloneDeep(oldNode.data);
        newData.node = newNode;
        return {
          ...oldNode,
          data: newData,
        };
      },
      true,
      () => {
        updateNodeInternals(nodeId);
      },
    );
  };

  return { handleOnNewValue };
};

export default useHandleOnNewValue;
