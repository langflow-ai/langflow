import "../assistantButton.css";
import { addEdge } from "@xyflow/react";
import { useAddComponent } from "@/hooks/use-add-component";
import useAssistantManagerStore from "@/stores/assistantManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import { getHandleId, scapedJSONStringfy } from "@/utils/reactflowUtils";
import ForwardedIconComponent from "../../genericIconComponent";
import ShadTooltip from "../../shadTooltipComponent";

interface PillProps {
  nudge;
  setNudgesOpen;
}

const Pill: React.FC<PillProps> = ({ nudge, setNudgesOpen }) => {
  const { templates } = useTypesStore();
  const addComponent = useAddComponent();
  const { selectedCompData } = useAssistantManagerStore();
  const onPillButtonClick = async () => {
    setNudgesOpen(false);
    switch (nudge.type) {
      case "connect_component": {
        addComponent(
          templates[nudge.trigger.componentId],
          nudge.trigger.componentId,
        );

        const nodes = useFlowStore.getState().nodes;
        const sourceNode = nodes[nodes.length - 1];
        const sourceNodeId = sourceNode.id;
        const sourceHandleObject = {
          dataType: sourceNode.data.type,
          id: sourceNode.id,
          name: sourceNode.data.node.outputs[0].name,
          output_types: sourceNode.data.node.outputs[0].types,
        };

        const targetNode = nodes.find((n) => n.id === selectedCompData.id);
        const targetField =
          targetNode.data.node.template[selectedCompData?.fieldName];

        const targetHandleObject = {
          fieldName: selectedCompData?.fieldName,
          id: selectedCompData.id,
          inputTypes: targetField.input_types,
          type: targetField.type,
        };

        // Create edge
        const sourceHandle = scapedJSONStringfy(sourceHandleObject);
        const targetHandle = scapedJSONStringfy(targetHandleObject);

        const edgeId = getHandleId(
          sourceNodeId,
          sourceHandle,
          selectedCompData.id,
          targetHandle,
        );

        const newEdge = {
          id: edgeId,
          source: sourceNodeId,
          target: selectedCompData.id,
          sourceHandle: sourceHandle,
          targetHandle: targetHandle,
          data: {
            sourceHandle: sourceHandleObject,
            targetHandle: targetHandleObject,
          },
        };

        // Add to flow
        useFlowStore.getState().setEdges((edges) => addEdge(newEdge, edges));
        break;
      }
      case "route":
      default:
        break;
    }
  };
  return (
    <ShadTooltip content={nudge.description}>
      <div
        id={nudge.id}
        className="pill rounded-md outline-none ring-ring focus-visible:ring-1"
      >
        <button
          className="flex cursor-point items-center gap-2 rounded-md p-1 px-2 bg-accent text-placeholder-foreground h-8"
          onClick={onPillButtonClick}
        >
          <ForwardedIconComponent
            name={nudge.ui.icon}
            className="h-[18px] w-[18px] shrink-0"
          ></ForwardedIconComponent>
          {nudge.display_text}
        </button>
      </div>
    </ShadTooltip>
  );
};

export default Pill;
