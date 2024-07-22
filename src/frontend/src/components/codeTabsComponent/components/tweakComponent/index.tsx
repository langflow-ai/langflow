import AccordionComponent from "@/components/accordionComponent";
import ShadTooltip from "@/components/shadTooltipComponent";
import { EditNodeComponent } from "@/modals/editNodeModal/components/editNodeComponent";
import { APIClassType } from "@/types/api";
import { NodeType } from "@/types/flow";

export function TweakComponent({
  open,
  node,
  setNode: setMyNode,
}: {
  open: boolean;
  node: NodeType;
  setNode: (
    id: string,
    update: NodeType | ((oldState: NodeType) => NodeType),
  ) => void;
}) {
  return node && node.data && node.data.node ? (
    <AccordionComponent
      trigger={
        <ShadTooltip side="top" styleClasses="z-50" content={node.data.id}>
          <div>{node.data.node?.display_name}</div>
        </ShadTooltip>
      }
      keyValue={node.data.id}
    >
      <EditNodeComponent
        open={open}
        autoHeight
        hideVisibility
        nodeClass={node.data.node}
        setNodeClass={(newNodeClass: APIClassType, type?: string) => {
          setMyNode(node.data.id, (old) => {
            return { ...old, node: newNodeClass };
          });
        }}
        setNode={(id, change) => {
          setMyNode(id, change);
        }}
        nodeId={node.data.id}
      />
    </AccordionComponent>
  ) : (
    <></>
  );
}
