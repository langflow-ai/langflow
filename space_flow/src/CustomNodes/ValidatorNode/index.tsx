import { Handle, Position } from "reactflow";

export default function ValidatorNode({ data }) {
    console.log(data)
  return (
    <div onClick={data.delete} className="validator-node relative bg-white h-16 w-40 border rounded-sm solid border-black flex flex-col justify-center">
      <Handle type="source" position={Position.Left}></Handle>
      <label className="absolute cursor-grab text-sm -top-3 left-1 bg-white w-14 text-center">
        Validator
      </label>
      <div className="w-full h-min text-xs text-center">
        validator data
      </div>
      <Handle type="target" position={Position.Right}></Handle>
    </div>
  );
}
