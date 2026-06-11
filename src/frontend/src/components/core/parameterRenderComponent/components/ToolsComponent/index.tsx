import { useState } from "react";
import { useTranslation } from "react-i18next";
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
  showParameter = true,
  hideButton = false,
  open,
  setOpen,
  // biome-ignore lint/suspicious/noExplicitAny: legacy
}: InputProps<any[] | undefined, ToolsComponentType>): JSX.Element | null {
  const { t } = useTranslation();
  const [internalOpen, setInternalOpen] = useState(false);
  const isModalOpen = open ?? internalOpen;
  const setIsModalOpen = setOpen ?? setInternalOpen;
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

  if (!showParameter) {
    return null;
  }

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
        className="relative flex items-center w-full gap-3"
        data-testid={"div-" + id}
      >
        {!hideButton && (visibleActions.length > 0 || isAction) && (
          <Button
            variant={
              ENABLE_MCP_COMPOSER && button_description ? "outline" : "ghost"
            }
            disabled={!value || disabled}
            size="sm"
            data-testid="button_open_actions"
            onClick={() => setIsModalOpen(true)}
            className={cn(
              "absolute -top-8 right-0 !text-mmd font-normal group-hover:text-primary",
              !button_description ? "text-muted-foreground" : "",
            )}
          >
            <ForwardedIconComponent
              name={
                ENABLE_MCP_COMPOSER && button_description
                  ? "wrench"
                  : "Settings2"
              }
              className="icon-size"
              strokeWidth={ICON_STROKE_WIDTH}
            />
            {button_description}
          </Button>
        )}

        {!value ? (
          <div className="flex w-full flex-wrap gap-1 overflow-hidden py-1.5">
            {[...Array(4)].map((_, index) => (
              <Skeleton key={index} className="h-6 w-20 rounded-full" />
            ))}
          </div>
        ) : visibleActions.length > 0 ? (
          <div
            className={cn(
              "flex w-full flex-wrap gap-1 overflow-hidden pb-1.5",
              hideButton ? "pt-0" : "pt-3",
            )}
          >
            {visibleActions.map((action, index) => (
              <Badge
                key={index}
                variant="secondaryStatic"
                size="sq"
                className="truncate font-normal"
                data-testid={testIdCase(`tool_${action.name}`)}
              >
                <span className="truncate text-xxs font-medium">
                  {(action.name === "unnamed"
                    ? t("common.unnamed")
                    : action.name
                  ).toUpperCase()}
                </span>
              </Badge>
            ))}
            {remainingCount > 0 && (
              <span className="ml-1 self-center text-xs font-normal text-muted-foreground">
                {t("input.moreActions", { count: remainingCount })}
              </span>
            )}
          </div>
        ) : (
          visibleActions.length === 0 &&
          isAction &&
          (hideButton ? (
            <span className="py-1.5 text-sm text-muted-foreground">
              {t("input.noActionsAddedToServer")}
            </span>
          ) : (
            <div className="mt-2 flex w-full flex-col items-center gap-2 rounded-md border border-dashed p-8">
              <span className="text-sm text-muted-foreground">
                {t("input.noActionsAddedToServer")}
              </span>
              <Button size={"sm"} onClick={() => setIsModalOpen(true)}>
                <span>{t("input.addActions")}</span>
              </Button>
            </div>
          ))
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
                  ? t("input.noActionsAvailable")
                  : t("input.selectActions"))}
            </span>
          </Button>
        )}
      </div>
    </div>
  );
}
