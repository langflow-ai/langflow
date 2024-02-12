import { cloneDeep } from "lodash";
import useFlowStore from "../../stores/flowStore";
import { IOInputProps } from "../../types/components";
import IOFileInput from "../IOInputs/FileInput";
import { Textarea } from "../ui/textarea";

export default function IOInputField({
  inputType,
  inputId,
}: IOInputProps): JSX.Element | undefined {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const node = nodes.find((node) => node.id === inputId);
  console.log(inputType);
  function handleInputType() {
    if (!node) return "no node found";
    switch (inputType) {
      case "TextInput":
        return (
          <Textarea
            className="h-full w-full custom-scroll"
            placeholder={"Enter text..."}
            value={node.data.node!.template["value"].value}
            onChange={(e) => {
              e.target.value;
              if (node) {
                let newNode = cloneDeep(node);
                newNode.data.node!.template["value"].value = e.target.value;
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
            className="h-full w-full custom-scroll"
            placeholder={"Enter text..."}
            value={node.data.node!.template["value"]}
            onChange={(e) => {
              e.target.value;
              if (node) {
                let newNode = cloneDeep(node);
                newNode.data.node!.template["value"].value = e.target.value;
                setNode(node.id, newNode);
              }
            }}
          />
        );
    }
  }
  return <div className="h-full w-full">{handleInputType()}</div>;
}
