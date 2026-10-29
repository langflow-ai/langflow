import HandleRenderComponent from "@/CustomNodes/GenericNode/components/handleRenderComponent";
import { getNodeInputColors } from "@/CustomNodes/helpers/get-node-input-colors";
import { getNodeInputColorsName } from "@/CustomNodes/helpers/get-node-input-colors-name";
import useFlowStore from "@/stores/flowStore";
import { useTypesStore } from "@/stores/typesStore";
import type { InputFieldType } from "@/types/api";

// A node field's handle, drawn beside one question card instead of on its own row.
export default function QuestionHandle({
  nodeId,
  fieldName,
  field,
  title,
}: {
  nodeId: string;
  fieldName: string;
  field: InputFieldType;
  title: string;
}) {
  const myData = useTypesStore((state) => state.data);
  const types = useTypesStore((state) => state.types);
  const setFilterEdge = useFlowStore((state) => state.setFilterEdge);
  return (
    <HandleRenderComponent
      left
      id={{
        inputTypes: field.input_types,
        type: field.type,
        id: nodeId,
        fieldName,
      }}
      title={title}
      tooltipTitle={field.input_types?.join("\n") ?? field.type}
      myData={myData}
      colors={getNodeInputColors(field.input_types, field.type, types)}
      colorName={getNodeInputColorsName(field.input_types, field.type, types)}
      setFilterEdge={setFilterEdge}
      showNode
      testIdComplement={`decision-question-${fieldName}`}
      nodeId={nodeId}
    />
  );
}
