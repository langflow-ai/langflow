import { useTweaksStore } from "@/stores/tweaksStore";
import { NodeType } from "@/types/flow";
import { TweakComponent } from "../tweakComponent";

export function TweaksComponent({ open }: { open: boolean }) {
  const nodes = useTweaksStore((state) => state.nodes);
  return (
    <div className="h-full w-full overflow-y-auto overflow-x-hidden rounded-lg bg-muted custom-scroll">
      {nodes?.map((node: NodeType, i) => (
        <div className="px-3" key={i}>
          <TweakComponent open={open} node={node} />
        </div>
      ))}
    </div>
  );
}
