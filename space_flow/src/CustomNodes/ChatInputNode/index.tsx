import {
  Bars3CenterLeftIcon,
} from "@heroicons/react/24/outline";
import { isValidConnection, nodeColors } from "../../utils";
import { Handle, Position } from "reactflow";
import Tooltip from "../../components/TooltipComponent";
import { typesContext } from "../../contexts/typesContext";
import { useContext } from "react";
import { NodeDataType } from "../../types/flow";

export default function ChatInputNode({ data }:{data:NodeDataType}) {
  const { types,reactFlowInstance } = useContext(typesContext);
  return (
    <div
      className="prompt-node relative rounded-lg solid border flex justify-center align-center py-3 px-6 bg-gray-50"
      style={{ color: nodeColors[types[data.type]] }}
    >
      <Tooltip title="Prefix: str">
        <Handle
          type="target"
          isValidConnection={(connection) =>
            isValidConnection(connection,reactFlowInstance)
          }
          position={Position.Left}
          id={"str|Prefix|" + data.id}
          className={"-ml-0.5 w-3 h-3 rounded-full border-2 bg-white"}
          style={{
            borderColor: nodeColors[types[data.type]],
          }}
        ></Handle>
      </Tooltip>
      <Tooltip title={"Message: str"}>
        <Handle
          type="source"
          isValidConnection={(connection) =>
            isValidConnection(connection,reactFlowInstance)
          }
          position={Position.Right}
          id={"str|str|" + data.id}
          className={"-mr-0.5  w-3 h-3 rounded-full border-2 bg-white"}
          style={{
            borderColor: nodeColors[types[data.type]],
          }}
        ></Handle>
      </Tooltip>
      <div
        className="flex gap-3 text-lg font-medium items-center"
        style={{ color: nodeColors[types[data.type]] }}
      >
        <Bars3CenterLeftIcon className="h-8 w-8 mt-1" />
        Input
      </div>
    </div>
  );
}
