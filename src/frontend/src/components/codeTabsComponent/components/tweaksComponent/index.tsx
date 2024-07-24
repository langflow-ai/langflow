import { useTweaksStore } from "@/stores/tweaksStore";
import { NodeType } from "@/types/flow";
import { classNames } from "@/utils/utils";
import { TweakComponent } from "../tweakComponent";

export function TweaksComponent({ open }: { open: boolean }) {
  const nodes = useTweaksStore((state) => state.nodes);
  return (
    <div className="api-modal-according-display">
      <div
        className={classNames(
          "h-[70vh] w-full overflow-y-auto overflow-x-hidden rounded-lg bg-muted custom-scroll",
        )}
      >
        {nodes?.map((node: NodeType, i) => (
          <div className="px-3" key={i}>
            <TweakComponent open={open} node={node} />
          </div>
        ))}
      </div>
    </div>
  );
}
