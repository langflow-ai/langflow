import {
  Bars3CenterLeftIcon,
  ChatBubbleBottomCenterTextIcon,
} from "@heroicons/react/24/outline";
import InputComponent from "../../components/inputComponent";
import { isValidConnection, nodeColors, snakeToNormalCase } from "../../utils";
import { Handle, Position } from "reactflow";
import Tooltip from "../../components/TooltipComponent";
import { typesContext } from "../../contexts/typesContext";
import { useContext } from "react";

export default function ChatInputNode({ data }) {
  const { types } = useContext(typesContext);
  return (
    <div
      className="prompt-node relative rounded-lg solid border flex justify-center align-center py-3 px-6 bg-gray-50"
      style={{ color: nodeColors[types[data.type]] }}
    >
      <Tooltip title="Prefix: str">
        <Handle
          type="target"
          isValidConnection={(connection) =>
            isValidConnection(data, connection)
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
            isValidConnection(data, connection)
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
