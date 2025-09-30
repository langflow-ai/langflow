import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import IconComponent from "@/components/common/genericIconComponent";
import sortFields from "@/CustomNodes/utils/sort-fields";
import { useTweaksStore } from "@/stores/tweaksStore";
import type { AllNodeType } from "@/types/flow";

interface FieldSelectorProps {
  componentId: string;
}

export function FieldSelector({ componentId }: FieldSelectorProps) {
  const nodes = useTweaksStore((state) => state.nodes);
  const setNode = useTweaksStore((state) => state.setNode);

  const selectedNode = useMemo(() => {
    return nodes?.find((node: AllNodeType) => node.data.id === componentId);
  }, [nodes, componentId]);

  const availableFields = useMemo(() => {
    if (!selectedNode?.data?.node?.template) return [];

    return Object.keys(selectedNode.data.node.template)
      .filter((key: string) => {
        const templateParam = selectedNode.data.node!.template[key] as any;
        return (
          key.charAt(0) !== "_" &&
          templateParam.show &&
          !(
            (key === "code" && templateParam.type === "code") ||
            (key.includes("code") && templateParam.proxy)
          )
        );
      })
      .sort((a, b) => sortFields(a, b, selectedNode.data.node!.field_order ?? []))
      .map((key: string) => {
        const templateParam = selectedNode.data.node!.template[key] as any;
        return {
          key,
          name: templateParam.name || key,
          display_name: templateParam.display_name || templateParam.name || key,
          description: templateParam.info || templateParam.description || "",
        };
      });
  }, [selectedNode]);

  const handleFieldToggle = (fieldKey: string) => {
    if (!selectedNode) return;

    const fieldTemplate = selectedNode.data.node!.template[fieldKey];
    const isCurrentlySelected = !fieldTemplate.advanced;
    
    // Create updated node with field toggle
    const updatedNode = {
      ...selectedNode,
      data: {
        ...selectedNode.data,
        node: {
          ...selectedNode.data.node!,
          template: {
            ...selectedNode.data.node!.template,
            [fieldKey]: {
              ...fieldTemplate,
              // Toggle advanced flag to control inclusion in tweaks
              advanced: isCurrentlySelected,
              // Keep the original value
              value: fieldTemplate.value || "",
            },
          },
        },
      },
    };
    
    // Update the node which will trigger updateTweaks
    setNode(componentId, updatedNode);
  };

  const isFieldSelected = (fieldKey: string) => {
    if (!selectedNode) return false;
    const fieldTemplate = selectedNode.data.node!.template[fieldKey];
    // Field is selected if it's not marked as advanced (which means it's included in tweaks)
    return !fieldTemplate.advanced;
  };

  if (!selectedNode) {
    return null;
  }

  const componentDisplayName = selectedNode?.data.node?.display_name || selectedNode?.data.id || '';

  return (
    <div className="flex flex-col gap-3">
      <div className="space-y-2 pr-2">
        {availableFields.map((field) => {
          const isSelected = isFieldSelected(field.key);
          
          return (
            <Button
              key={field.key}
              variant="ghost"
              className={`flex h-auto w-full justify-start gap-3 p-3 text-left border rounded-lg ${
                isSelected 
                  ? "bg-accent border-accent-foreground/20" 
                  : "bg-muted/50 border-border/50 hover:bg-muted/80"
              }`}
              onClick={() => handleFieldToggle(field.key)}
            >
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div className="font-medium truncate">{field.display_name}</div>
                {field.description && (
                  <div className="text-xs text-muted-foreground line-clamp-2 overflow-hidden text-ellipsis">
                    {field.description}
                  </div>
                )}
              </div>
              {isSelected && (
                <IconComponent name="Check" className="h-4 w-4 text-accent-foreground" />
              )}
            </Button>
          );
        })}
        
        {availableFields.length === 0 && (
          <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
            No configurable fields available for this component
          </div>
        )}
      </div>
    </div>
  );
}