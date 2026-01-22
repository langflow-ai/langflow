import type { CustomCellRendererProps } from "ag-grid-react";
import useHandleOnNewValue from "@/CustomNodes/hooks/use-handle-new-value";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Input } from "@/components/ui/input";
import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import { cn } from "@/utils/utils";
import ToggleShadComponent from "../../../toggleShadComponent";

export default function TableMcpDescriptionCellRender({
  value: { nodeId, fieldKey, isTweaks },
}: CustomCellRendererProps) {
  const node = useFlowStore((state) => state.getNode(nodeId));
  const parameter = node?.data?.node?.template?.[fieldKey];
  const mcpEnabled = parameter?.mcp_enabled ?? false;
  const mcpDescription = parameter?.mcp_description ?? "";
  const mcpRequired = parameter?.mcp_required ?? false;

  const { handleOnNewValue } = useHandleOnNewValue({
    node: node?.data.node as APIClassType,
    nodeId,
    name: fieldKey,
    setNode: isTweaks ? () => {} : undefined,
  });

  const handleMcpEnabledChange = (changes: { value?: boolean } | boolean) => {
    const enabled =
      typeof changes === "object" ? (changes?.value ?? false) : changes;
    handleOnNewValue({
      mcp_enabled: enabled,
    });
  };

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleOnNewValue({
      mcp_description: e.target.value,
    });
  };

  const handleMcpRequiredChange = (changes: { value?: boolean } | boolean) => {
    const required =
      typeof changes === "object" ? (changes?.value ?? false) : changes;
    handleOnNewValue({
      mcp_required: required,
    });
  };

  if (!("mcp_enabled" in parameter)) {
    // if the component doesn't have the attribute mcp_enabled, it doesn't have the MCP Input Mixin, then return null
    return null;
  }

  return (
    <div
      className={cn(
        "group mx-auto flex h-full w-full items-center gap-2 px-1 py-2.5",
        isTweaks && "pointer-events-none opacity-30",
      )}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-center">
        <ShadTooltip
          content="Enable this field to be used as MCP tool call argument"
          styleClasses="z-50"
        >
          <div className="flex h-full w-full items-center justify-center">
            <ToggleShadComponent
              value={mcpEnabled}
              handleOnNewValue={handleMcpEnabledChange}
              disabled={isTweaks}
              editNode={true}
              id={`mcp-enabled-${fieldKey}`}
            />
          </div>
        </ShadTooltip>
      </div>
      {mcpEnabled && (
        <>
          <Input
            value={mcpDescription}
            onChange={handleDescriptionChange}
            placeholder="MCP Description..."
            disabled={isTweaks}
            className="input-edit-node flex-1"
          />
          <div className="flex items-center justify-center">
            <ShadTooltip
              content="Mark this field as required for MCP tool call."
              styleClasses="z-50"
            >
              <div className="flex h-full w-full items-center justify-center">
                <ToggleShadComponent
                  value={mcpRequired}
                  handleOnNewValue={handleMcpRequiredChange}
                  disabled={isTweaks}
                  editNode={true}
                  id={`mcp-required-${fieldKey}`}
                />
              </div>
            </ShadTooltip>
          </div>
        </>
      )}
    </div>
  );
}
