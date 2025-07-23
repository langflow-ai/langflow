import { useState } from "react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { ENABLE_MCP_COMPOSER } from "@/customization/feature-flags";
import ToolsModal from "@/modals/toolsModal";
import { cn, testIdCase } from "@/utils/utils";
import { ForwardedIconComponent } from "../../../../common/genericIconComponent";
import { Badge } from "../../../../ui/badge";
import { Button } from "../../../../ui/button";
import { Skeleton } from "../../../../ui/skeleton";
import type { InputProps, ToolsComponentType } from "../../types";

export default function ToolsComponent({
  description,
  value,
  editNode = false,
  id = "",
  handleOnNewValue,
  isAction = false,
  placeholder,
  button_description,
  title,
  icon,
  disabled = false,
  template,
}: InputProps<any[] | undefined, ToolsComponentType>): JSX.Element {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const actions = value
    ?.filter((action) => action.status === true)
    .map((action) => {
      return {
        name: action.name,
        tags: action.tags,
        description: action.description,
      };
    });

  const visibleActionsQt = isAction ? 20 : 4;

  const visibleActions = actions?.slice(0, visibleActionsQt) || [];
  const remainingCount = actions
    ? Math.max(0, actions.length - visibleActionsQt)
    : 0;

  return (
    <div
      className={cn(
        "flex w-full items-center",
        disabled && "cursor-not-allowed",
      )}
    >
      <ToolsModal
        open={isModalOpen}
        placeholder={placeholder || ""}
        setOpen={setIsModalOpen}
        isAction={isAction}
        description={description}
        rows={value || []}
        handleOnNewValue={handleOnNewValue}
        title={title}
        icon={icon}
      />
      <div
        className="relative flex flex-col w-full gap-3"
        data-testid={"div-" + id}
      >
        <div className="flex flex-row justify-between">
          <div className="flex flex-row justify-between">
            <ShadTooltip
              content="Flows in this project can be exposed as callable MCP tools."
              side="right"
            >
              <div
                className={cn(
                  "flex items-center hover:cursor-help",
                  !ENABLE_MCP_COMPOSER && "text-mmd",
                )}
              >
                Flows/Tools
                <ForwardedIconComponent
                  name="info"
                  className="ml-1.5 h-4 w-4 text-muted-foreground"
                  aria-hidden="true"
                />
              </div>
            </ShadTooltip>
          </div>
          {(visibleActions.length > 0 || isAction) && (
            <Button
              variant={ENABLE_MCP_COMPOSER ? "outline" : "ghost"}
              disabled={!value || disabled}
              size="sm"
              data-testid="button_open_actions"
              onClick={() => setIsModalOpen(true)}
            >
              <ForwardedIconComponent
                name={ENABLE_MCP_COMPOSER ? "wrench" : "Settings2"}
                className="icon-size"
                strokeWidth={ICON_STROKE_WIDTH}
              />
              {button_description}
            </Button>
          )}
        </div>
        {!value ? (
          <div className="flex w-full flex-wrap gap-1 overflow-hidden py-1.5">
            {[...Array(4)].map((_, index) => (
              <Skeleton key={index} className="h-6 w-20 rounded-full" />
            ))}
          </div>
        ) : visibleActions.length > 0 ? (
          <div className="flex w-full flex-wrap gap-1 overflow-hidden py-1.5">
            {visibleActions.map((action, index) => (
              <Badge
                key={index}
                variant="secondaryStatic"
                size="sq"
                className="truncate font-normal"
                data-testid={testIdCase(`tool_${action.name}`)}
              >
                <span className="truncate text-xxs font-medium">
                  {action.name.toUpperCase()}
                </span>
              </Badge>
            ))}
            {remainingCount > 0 && (
              <span className="ml-1 self-center text-xs font-normal text-muted-foreground">
                +{remainingCount} more
              </span>
            )}
          </div>
        ) : (
          visibleActions.length === 0 &&
          isAction && (
            <div className="mt-2 flex w-full flex-col items-center gap-2 rounded-md border border-dashed p-8">
              <span className="text-sm text-muted-foreground">
                No actions added to this server
              </span>
              <Button size={"sm"} onClick={() => setIsModalOpen(true)}>
                <span>Add actions</span>
              </Button>
            </div>
          )
        )}

        {visibleActions.length === 0 && !isAction && value && (
          <Button
            disabled={disabled || value.length === 0}
            size={editNode ? "xs" : "default"}
            className={
              "w-full " +
              (disabled ? "pointer-events-none cursor-not-allowed" : "")
            }
            onClick={() => setIsModalOpen(true)}
          >
            <span>
              {placeholder ||
                (value.length === 0
                  ? "No actions available"
                  : "Select actions")}
            </span>
          </Button>
        )}
      </div>
    </div>
  );
}
