import { Handle, Position } from "reactflow";

export default function ModelNode({ data }) {
    console.log(data)
  return (
    <div onClick={data.delete} className="model-Node relative bg-white h-16 w-40 border rounded-sm solid border-black flex flex-col justify-center">
      <Handle type="source" position={Position.Left}></Handle>
      <label className="absolute cursor-grab text-sm -top-3 left-1 bg-white w-14 text-center">
        Model
      </label>
      <div className="w-full h-min text-xs text-center">
        {data.llm.model_name}
      </div>
      <Handle type="target" position={Position.Right}></Handle>
    </div>
  );
}
