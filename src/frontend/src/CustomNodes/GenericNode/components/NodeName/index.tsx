import InputComponent from "@/components/inputComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useEffect, useState } from "react";

export default function NodeName({
  display_name,
  selected,
  nodeId,
}: {
  display_name?: string;
  selected: boolean;
  nodeId: string;
}) {
  const [inputName, setInputName] = useState(false);
  const [nodeName, setNodeName] = useState(display_name);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const setNode = useFlowStore((state) => state.setNode);
  useEffect(() => {
    if (!selected) {
      setInputName(false);
    }
  }, [selected]);

  useEffect(() => {
    setNodeName(display_name);
  }, [display_name]);

  return inputName ? (
    <div className="w-full">
      <InputComponent
        onBlur={() => {
          setInputName(false);
          if (nodeName?.trim() !== "") {
            setNodeName(nodeName);
            setNode(nodeId, (old) => ({
              ...old,
              data: {
                ...old.data,
                node: {
                  ...old.data.node,
                  display_name: nodeName,
                },
              },
            }));
          } else {
            setNodeName(display_name);
          }
        }}
        value={nodeName}
        autoFocus
        onChange={setNodeName}
        password={false}
        blurOnEnter={true}
        id={`input-title-${display_name}`}
      />
    </div>
  ) : (
    <div className="group flex w-full items-center gap-1">
      <ShadTooltip content={display_name}>
        <div
          onDoubleClick={(event) => {
            setInputName(true);
            takeSnapshot();
            event.stopPropagation();
            event.preventDefault();
          }}
          data-testid={"title-" + display_name}
          className="nodoubleclick w-full cursor-text truncate text-primary"
        >
          {display_name}
        </div>
      </ShadTooltip>
    </div>
  );
}
