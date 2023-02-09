import { Handle, Position } from "reactflow";

export default function PromptNode({ data }) {
    console.log(data)
  return (
    <div
      onClick={()=>data.onClick()}
      className="prompt-Node relative bg-white h-16 w-40 border rounded-sm solid border-black flex flex-col justify-center"
    >
      <Handle type="target" position={Position.Left}></Handle>
      <label className="absolute cursor-grab text-sm -top-3 left-1 bg-white w-14 text-center">
        {" "}
        Prompt
      </label>
      <div className="w-full h-10 truncate bg-slate-50 text-xs">
        {" "}
        {data.template}
      </div>
      <Handle type="source" position={Position.Right}></Handle>
    </div>
  );
}
