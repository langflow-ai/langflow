import { useTweaksStore } from "@/stores/tweaksStore";
import type { AllNodeType } from "@/types/flow";
import { TweakComponent } from "../tweakComponent";

export function TweaksComponent({ open }: { open: boolean }) {
  const nodes = useTweaksStore((state) => state.nodes);
  return nodes?.map((node: AllNodeType, i) => (
    <div className="px-3" key={i}>
      <TweakComponent open={open} node={node} />
    </div>
  ));
}
