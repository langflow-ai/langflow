import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import ToolsComponent from "@/components/core/parameterRenderComponent/components/ToolsComponent";
import { Button } from "@/components/ui/button";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { ENABLE_MCP_COMPOSER } from "@/customization/feature-flags";
import type { InputFieldType } from "@/types/api";
import type { ToolFlow } from "../utils/mcpServerUtils";

interface McpFlowsSectionProps {
  flowsMCPData: ToolFlow[];
  handleOnNewValue: (changes: Partial<InputFieldType>) => void;
}

export const McpFlowsSection = ({
  flowsMCPData,
  handleOnNewValue,
}: McpFlowsSectionProps) => {
  const { t } = useTranslation();
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <div className="w-full pr-4 xl:w-2/5">
      <div className="flex flex-row items-center justify-between">
        <ShadTooltip content={t("mcp.flowsTooltip")} side="right">
          <div className="flex items-center text-sm font-medium hover:cursor-help">
            {t("mcp.flowsTools")}
            <ForwardedIconComponent
              name="info"
              className="ml-1.5 h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
          </div>
        </ShadTooltip>
        <Button
          variant={ENABLE_MCP_COMPOSER ? "outline" : "ghost"}
          size="sm"
          data-testid="button_open_actions"
          onClick={() => setIsModalOpen(true)}
          className="!text-mmd font-normal"
        >
          <ForwardedIconComponent
            name={ENABLE_MCP_COMPOSER ? "wrench" : "Settings2"}
            className="icon-size"
            strokeWidth={ICON_STROKE_WIDTH}
          />
          {t("mcp.editTools")}
        </Button>
      </div>
      <div className="flex flex-row flex-wrap gap-2 pt-4">
        <ToolsComponent
          value={flowsMCPData}
          title={t("mcp.toolsTitle")}
          description={t("mcp.toolsDescription")}
          handleOnNewValue={handleOnNewValue}
          id="mcp-server-tools"
          button_description={t("mcp.editTools")}
          editNode={false}
          isAction
          disabled={false}
          hideButton
          open={isModalOpen}
          setOpen={setIsModalOpen}
        />
      </div>
    </div>
  );
};
