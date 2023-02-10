import { Handle, Position } from "reactflow";
import { useContext } from "react";
import { PopUpContext } from "../../context/popUpContext";


export default function PromptNode({ data }) {
  const {openPopUp} = useContext(PopUpContext)
  return (
    <div
      onClick={()=>openPopUp(<div className="absolute top-1/2 left-1/2">teste</div>)}
      className="prompt-Node relative bg-white h-16 w-40 border rounded-sm solid border-black flex flex-col justify-center"
    >
      <Handle type="source" position={Position.Left}></Handle>
      <label className="absolute cursor-grab text-sm -top-3 left-1 bg-white w-14 text-center">
        Prompt
      </label>
      <div className="w-full h-10 truncate bg-slate-50 text-xs">
        {data.template}
      </div>
      <Handle type="target" position={Position.Right}></Handle>
    </div>
  );
}
