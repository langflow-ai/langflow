import { useTweaksStore } from "@/stores/tweaksStore";
import { AllNodeType } from "@/types/flow";
import { TweakComponent } from "../tweakComponent";

export function TweaksComponent({ open }: { open: boolean }) {
  const nodes = useTweaksStore((state) => state.nodes);
  return (
    <div className="bg-muted custom-scroll h-full w-full overflow-x-hidden overflow-y-auto rounded-lg">
      {nodes?.map((node: AllNodeType, i) => (
        <div className="px-3" key={i}>
          <TweakComponent open={open} node={node} />
        </div>
      ))}
    </div>
  );
}
