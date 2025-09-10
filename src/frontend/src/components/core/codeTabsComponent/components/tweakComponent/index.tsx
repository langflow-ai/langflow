import { useEffect, useState } from "react";
import AccordionComponent from "@/components/common/accordionComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { EditNodeComponent } from "@/modals/editNodeModal/components/editNodeComponent";
import type { APIClassType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import { getEffectiveAliasFromAnyNode } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";

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

  // Get alias info for badge display
  const effectiveAlias = getEffectiveAliasFromAnyNode(node);
  const aliasNumber = effectiveAlias?.match(/#(\d+)$/)?.[1];
  const displayName = node.data.node?.display_name || "";

  return node && node.data && nodeClass ? (
    <AccordionComponent
      trigger={
        <ShadTooltip side="top" styleClasses="z-50" content={node.data.id}>
          <div className="flex items-center gap-2 text-primary">
            <span>{displayName}</span>
            {aliasNumber && (
              <div className="flex h-5 w-auto min-w-[18px] items-center justify-center rounded border border-border bg-background px-1.5 text-xs font-semibold text-foreground">
                #{aliasNumber}
              </div>
            )}
          </div>
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
