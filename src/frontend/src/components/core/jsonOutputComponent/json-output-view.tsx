import React from "react";
import JsonEditor from "../jsonEditor";
import useFlowStore from "@/stores/flowStore";
import { APIClassType } from "@/types/api";

interface JsonOutputViewComponentProps {
  data: string | object;
  width?: string;
  height?: string;
  nodeId: string;
  outputName: string;
}

const JsonOutputViewComponent: React.FC<JsonOutputViewComponentProps> = ({
  data,
  width = "100%",
  height = "600px",
  nodeId,
  outputName,
}) => {
  const jsonData = typeof data === "string" ? JSON.parse(data) : data;
  const setNode = useFlowStore((state) => state.setNode);
  const node = useFlowStore((state) => state.getNode(nodeId));
  const outputs = (node?.data.node as APIClassType)?.outputs;
  const output = outputs?.find(o => o.name === outputName);
  const initialFilter = output?.options?.filter;

  return (
    <JsonEditor
      data={{ json: jsonData }}
      readOnly={true}
      width={width}
      height={height}
      className="rounded border border-border"
      setFilter={(filter) => {
        setNode(nodeId, (old) => {
          const outputs = (old.data.node as APIClassType).outputs;
          const output = outputs?.find(o => o.name === outputName);
          if (output) {
            output.options = {
              ...output.options,
              filter: filter,
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
  );
};

export default JsonOutputViewComponent;
