import { ICON_STROKE_WIDTH } from "@/constants/constants";
import ToolsModal from "@/modals/toolsModal";
import { cn } from "@/utils/utils";
import { useState } from "react";
import { ForwardedIconComponent } from "../../../../common/genericIconComponent";
import { Badge } from "../../../../ui/badge";
import { Button } from "../../../../ui/button";
import { InputProps, ToolsComponentType } from "../../types";

export default function ToolsComponent({
  description,
  value,
  editNode = false,
  id = "",
  handleOnNewValue,
  isAction = false,
  button_description,
  title,
  icon,
  disabled = false,
}: InputProps<any[], ToolsComponentType>): JSX.Element {
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

  const visibleActions = actions?.slice(0, 4) || [];
  const remainingCount = actions ? Math.max(0, actions.length - 4) : 0;

  return (
    <div
      className={
        "flex w-full items-center" + (disabled ? " cursor-not-allowed" : "")
      }
    >
      <ToolsModal
        open={isModalOpen}
        setOpen={setIsModalOpen}
        isAction={isAction}
        description={description}
        rows={value}
        handleOnNewValue={handleOnNewValue}
        title={title}
        icon={icon}
      />
      <div
        className="relative flex w-full items-center gap-3"
        data-testid={"div-" + id}
      >
        {visibleActions.length > 0 && (
          <Button
            variant={"ghost"}
            size={"iconMd"}
            className={cn(
              "absolute -top-8 right-0 font-semibold text-muted-foreground group-hover:text-primary",
            )}
            data-testid="button_open_actions"
            onClick={() => setIsModalOpen(true)}
          >
            <ForwardedIconComponent
              name="Settings2"
              className="icon-size"
              strokeWidth={ICON_STROKE_WIDTH}
            />
            {button_description}
          </Button>
        )}
        {visibleActions.length > 0 && (
          <div className="flex w-full flex-wrap gap-1 overflow-hidden py-1.5">
            {visibleActions.map((action, index) => (
              <Badge
                key={index}
                variant="secondaryStatic"
                size="sq"
                className="truncate font-normal"
              >
                <span className="truncate">{action.name}</span>
              </Badge>
            ))}
            {remainingCount > 0 && (
              <span className="ml-1 self-center text-xs font-normal text-muted-foreground">
                +{remainingCount} more
              </span>
            )}
          </div>
        )}

        {visibleActions.length === 0 && (
          <Button
            disabled={disabled}
            size={editNode ? "xs" : "default"}
            className={
              "w-full " +
              (disabled ? "pointer-events-none cursor-not-allowed" : "")
            }
            onClick={() => setIsModalOpen(true)}
          >
            <span>Select actions</span>
          </Button>
        )}
      </div>
    </div>
  );
}
