import { ChatBubbleBottomCenterTextIcon } from "@heroicons/react/24/outline";
import { Handle, Position } from "reactflow";
import Input from "../../components/inputComponent";
import { isValidConnection, snakeToNormalCase } from "../../utils";
import Tooltip from "../../components/TooltipComponent";

export default function ChatOutputNode({ data }) {
  return (
    <div className="prompt-node relative rounded-lg solid border flex justify-center align-center py-3 px-6 bg-blue-600">
      <Tooltip title="Message: str">
        <Handle
          type="source"
          isValidConnection={(connection) => isValidConnection(data,connection)}
          position={Position.Left}
          id={"str|output|"+data.id}
          className="ml-1 bg-transparent border-solid border-l-8 border-l-white border-y-transparent border-y-8 border-r-0 rounded-none"
        ></Handle>
      </Tooltip>

      <div className="flex gap-3 text-lg font-medium text-white items-center">
        Output
        <ChatBubbleBottomCenterTextIcon className="h-8 w-8 mt-1" />
      </div>
    </div>
  );
}
