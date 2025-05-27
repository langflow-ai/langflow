import AccordionComponent from "@/components/common/accordionComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { EditNodeComponent } from "@/modals/editNodeModal/components/editNodeComponent";
import { APIClassType } from "@/types/api";
import { AllNodeType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";
import { useEffect, useState } from "react";

export function TweakComponent({
  open,
  node,
}: {
  open: boolean;
  node: AllNodeType;
}) {
  const [nodeClass, setNodeClass] = useState<APIClassType | undefined>(
    node.data?.node,
  );

  useEffect(() => {
    if (
      customStringify(Object.keys(node.data?.node?.template ?? {})) ===
      customStringify(Object.keys(nodeClass?.template ?? {}))
    )
      return;
    setNodeClass(node.data?.node);
  }, [node.data?.node]);
  return node && node.data && nodeClass ? (
    <AccordionComponent
      trigger={
        <ShadTooltip side="top" styleClasses="z-50" content={node.data.id}>
          <div className="text-primary">{node.data.node?.display_name}</div>
        </ShadTooltip>
      }
      keyValue={node.data.id}
    >
      <EditNodeComponent
        open={open}
        autoHeight
        nodeClass={nodeClass}
        isTweaks
        nodeId={node.data.id}
      />
    </AccordionComponent>
  ) : (
    <></>
  );
}
