import { cloneDeep } from "lodash";
import { Textarea } from "../../../../components/ui/textarea";
import { InputOutput } from "../../../../constants/enums";
import useFlowStore from "../../../../stores/flowStore";
import { IOFieldViewProps } from "../../../../types/components";
import IOFileInput from "./components/FileInput";

export default function IOFieldView({
  type,
  fieldType,
  fieldId,
  left,
}: IOFieldViewProps): JSX.Element | undefined {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const node = nodes.find((node) => node.id === fieldId);
  function handleOutputType() {
    if (!node) return <>"No node found!"</>;
    switch (type) {
      case InputOutput.INPUT:
        switch (fieldType) {
          case "TextInput":
            return (
              <Textarea
                className={`w-full custom-scroll ${
                  left ? " min-h-32" : " h-full"
                }`}
                placeholder={"Enter text..."}
                value={node.data.node!.template["input_value"].value}
                onChange={(e) => {
                  e.target.value;
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["input_value"].value =
                      e.target.value;
                    setNode(node.id, newNode);
                  }
                }}
              />
            );
          case "FileLoader":
            return (
              <IOFileInput
                field={node.data.node!.template["file_path"]["value"]}
                updateValue={(e) => {
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["file_path"].value = e;
                    setNode(node.id, newNode);
                  }
                }}
              />
            );

          default:
            return (
              <Textarea
                className={`w-full custom-scroll ${
                  left ? " min-h-32" : " h-full"
                }`}
                placeholder={"Enter text..."}
                value={node.data.node!.template["input_value"]}
                onChange={(e) => {
                  e.target.value;
                  if (node) {
                    let newNode = cloneDeep(node);
                    newNode.data.node!.template["input_value"].value =
                      e.target.value;
                    setNode(node.id, newNode);
                  }
                }}
              />
            );
        }
      case InputOutput.OUTPUT:
        switch (fieldType) {
          case "TextOutput":
            return (
              <Textarea
                className={`w-full custom-scroll ${
                  left ? " min-h-32" : " h-full"
                }`}
                placeholder={"Empty"}
                // update to real value on flowPool
                value={
                  (flowPool[node.id] ?? [])[
                    (flowPool[node.id]?.length ?? 1) - 1
                  ]?.data.results.result ?? ""
                }
                readOnly
              />
            );

          default:
            return (
              <Textarea
                className={`w-full custom-scroll ${
                  left ? " min-h-32" : " h-full"
                }`}
                placeholder={"Empty"}
                // update to real value on flowPool
                value={
                  (flowPool[node.id] ?? [])[
                    (flowPool[node.id]?.length ?? 1) - 1
                  ]?.data.results.result ?? ""
                }
                readOnly
              />
            );
        }
      default:
        break;
    }
  }
  return handleOutputType();
}
