import { ChatBubbleBottomCenterTextIcon } from "@heroicons/react/24/outline";
import { Handle, Position } from "reactflow";
import Input from "../../components/inputComponent";
import { snakeToNormalCase } from "../../utils";

export default function ChatOutputNode({ data }) {

    return (
        <div className="prompt-node relative rounded-lg solid border flex justify-center align-center py-3 px-6 bg-blue-600">
        <Handle
          type="source"
          position={Position.Left}
          id="b"
          className="ml-1 bg-transparent border-solid border-l-8 border-l-white border-y-transparent border-y-8 border-r-0 rounded-none"
        ></Handle>
        <div className="flex gap-3 text-lg font-medium text-white items-center">
          Output
          <ChatBubbleBottomCenterTextIcon className="h-8 w-8 mt-1" />
        </div>
      </div>
    );

}