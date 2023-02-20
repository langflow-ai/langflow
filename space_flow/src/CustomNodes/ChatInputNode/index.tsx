import { Bars3CenterLeftIcon, ChatBubbleBottomCenterTextIcon } from "@heroicons/react/24/outline";
import InputComponent from "../../components/inputComponent";
import { isValidConnection, nodeColors, snakeToNormalCase } from "../../utils";
import { Handle, Position } from "reactflow";
import Tooltip from "../../components/TooltipComponent";
import { typesContext } from "../../contexts/typesContext";
import { useContext } from "react";

export default function ChatInputNode({ data }) {
  const {types} = useContext(typesContext);
  return (
    <div className="prompt-node relative rounded-lg solid border flex justify-center align-center py-3 px-6 bg-gray-50" style={{color: nodeColors[types[data.type]]}}>
      <Tooltip title="Prefix: str">
        <Handle
          type="source"
          position={Position.Left}
          id={"str|Prefix|" + data.id}
          isValidConnection={(connection) =>
            isValidConnection(data, connection)
          }
          className="ml-1 bg-transparent border-solid border-l-8 border-y-transparent border-y-8 border-r-0 rounded-none"
          style={{ borderLeftColor: nodeColors[types[data.type]] }}
        ></Handle>
      </Tooltip>
        <Tooltip title={"Message: str"}>
      <Handle
        type="target"
        position={Position.Right}
        id={'str|str|'+data.id}
        isValidConnection={(connection) => isValidConnection(data,connection)}
        className="-mr-1 bg-transparent border-solid border-l-8 border-y-transparent border-y-8 border-r-0 rounded-none"
        style={{borderLeftColor: nodeColors[types[data.type]]}}
      ></Handle>
      </Tooltip>
      <div className="flex gap-3 text-lg font-medium items-center" style={{color: nodeColors[types[data.type]]}}>
        <Bars3CenterLeftIcon className="h-8 w-8 mt-1" />
        Input
      </div>
    </div>
  );
}
