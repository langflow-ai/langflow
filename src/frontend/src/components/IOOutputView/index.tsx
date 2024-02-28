import { cloneDeep } from "lodash";
import useFlowStore from "../../stores/flowStore";
import { IOOutputProps } from "../../types/components";
import { Textarea } from "../ui/textarea";

export default function IOOutputView({
  outputType,
  outputId,
}: IOOutputProps): JSX.Element | undefined {
  const nodes = useFlowStore((state) => state.nodes);
  const setNode = useFlowStore((state) => state.setNode);
  const flowPool = useFlowStore((state) => state.flowPool);
  const node = nodes.find((node) => node.id === outputId);
  function handleOutputType() {
    if (!node) return <>"No node found!"</>;
    switch (outputType) {
      case "TextOutput":
        return (
          <Textarea
            className="w-full custom-scroll"
            placeholder={"Empty"}
            // update to real value on flowPool
            value={((flowPool[node.id] ?? [])[(flowPool[node.id]?.length ?? 1) - 1])?.params ?? ""}
            readOnly
          />
        );

      default:
        return (
          <Textarea
            className="w-full custom-scroll"
            placeholder={"Enter text..."}
            value={node.data.node!.template["input_value"]}
            onChange={(e) => {
              e.target.value;
              if (node) {
                let newNode = cloneDeep(node);
                newNode.data.node!.template["input_value"].value = e.target.value;
                setNode(node.id, newNode);
              }
            }}
          />
        );
    }
  }
  return handleOutputType();
}
