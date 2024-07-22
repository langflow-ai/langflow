import { NodeType } from "@/types/flow";
import { classNames } from "@/utils/utils";
import { TweakComponent } from "../tweakComponent";

export function TweaksComponent({
  nodes,
  setNodes,
  tweaks,
  open,
}: {
  nodes: NodeType[] | undefined;
  setNodes: React.Dispatch<React.SetStateAction<NodeType[] | undefined>>;
  tweaks: string[];
  open: boolean;
}) {
  return (
    <div className="api-modal-according-display">
      <div
        className={classNames(
          "h-[70vh] w-full overflow-y-auto overflow-x-hidden rounded-lg bg-muted custom-scroll",
        )}
      >
        {nodes?.map((node: NodeType, i) => (
          <div className="px-3" key={i}>
            {node.data?.node && tweaks.includes(node.data.id) && (
              <TweakComponent
                open={open}
                node={node}
                setNode={(id, change) => {
                  if (setNodes) {
                    setNodes((prevNodes) => {
                      if (prevNodes) {
                        let newChange =
                          typeof change === "function"
                            ? change(prevNodes.find((node) => node.id === id)!)
                            : change;
                        return prevNodes.map((n) => {
                          if (n.data.id === id) {
                            return newChange;
                          }
                          return n;
                        });
                      }
                      return prevNodes;
                    });
                  }
                }}
              />
            )}

            {tweaks.length === 0 && (
              <>
                <div className="pt-3">
                  No tweaks are available for this flow.
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
