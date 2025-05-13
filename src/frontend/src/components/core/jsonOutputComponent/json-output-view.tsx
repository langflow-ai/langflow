import useFlowStore from "@/stores/flowStore";
import { APIClassType } from "@/types/api";
import React from "react";
import JsonEditor from "../jsonEditor";

interface JsonOutputViewComponentProps {
  data: string | object;
  width?: string;
  height?: string;
  nodeId: string;
  outputName: string;
}

const JsonOutputViewComponent: React.FC<JsonOutputViewComponentProps> = ({
  data,
  nodeId,
  outputName,
}) => {
  const jsonData = typeof data === "string" ? JSON.parse(data) : data;
  const setNode = useFlowStore((state) => state.setNode);
  const node = useFlowStore((state) => state.getNode(nodeId));
  const outputs = (node?.data.node as APIClassType)?.outputs;
  const output = outputs?.find((o) => o.name === outputName);
  const initialFilter = output?.options?.filter;

  return (
    <div className="flex h-full flex-1 flex-col">
      <JsonEditor
        data={{ json: jsonData }}
        readOnly={true}
        className="flex-1 rounded border border-border"
        setFilter={(filter) => {
          setNode(nodeId, (old) => {
            const outputs = (old.data.node as APIClassType).outputs;
            const output = outputs?.find((o) => o.name === outputName);
            if (output) {
              output.options = {
                ...output.options,
                filter: filter !== "" ? filter : undefined,
              };
            }
            return {
              ...old,
              data: {
                ...old.data,
                node: {
                  ...old.data.node,
                  outputs: outputs,
                },
              },
            };
          });
        }}
        allowFilter={true}
        initialFilter={initialFilter}
      />
    </div>
  );
};

export default JsonOutputViewComponent;
