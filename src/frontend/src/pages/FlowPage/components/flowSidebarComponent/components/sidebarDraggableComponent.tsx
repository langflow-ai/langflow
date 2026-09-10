import { type DragEventHandler, forwardRef, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent, {
  ForwardedIconComponent,
} from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import {
  useIsFlowPermissionPending,
  useIsFlowReadOnly,
} from "@/contexts/permissionsContext";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import { useAddComponent } from "@/hooks/use-add-component";
import { useDarkStore } from "@/stores/darkStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { APIClassType } from "@/types/api";
import {
  createFlowComponent,
  downloadNode,
  getNodeId,
} from "@/utils/reactflowUtils";
import { cn, removeCountFromString } from "@/utils/utils";

export const SidebarDraggableComponent = forwardRef(
  (
    {
      sectionName,
      display_name,
      icon,
      itemName,
      error,
      color,
      onDragStart,
      apiClass,
      official,
      onDelete,
      beta,
      legacy,
      disabled,
      disabledTooltip,
    }: {
      sectionName: string;
      apiClass: APIClassType;
      icon: string;
      display_name: string;
      itemName: string;
      error: boolean;
      color: string;
      onDragStart: DragEventHandler<HTMLDivElement>;
      official: boolean;
      onDelete?: () => void;
      beta: boolean;
      legacy: boolean;
      disabled?: boolean;
      disabledTooltip?: string;
    },
    ref,
  ) => {
    const { t } = useTranslation();
    const [open, setOpen] = useState(false);
    const { deleteFlow } = useDeleteFlow();
    const flows = useFlowsManagerStore((state) => state.flows);
    const addComponent = useAddComponent();
    // Same flow id `useAddComponent` gates on, so the affordance and the gate
    // can never disagree about which flow is being evaluated.
    const currentFlowId = useFlowStore((state) => state.currentFlow?.id);
    const isReadOnly = useIsFlowReadOnly(currentFlowId);
    const isPermissionPending = useIsFlowPermissionPending(currentFlowId);

    // `isReadOnly` is the same predicate the add path refuses on, so the
    // control is unavailable for exactly as long as the click would be
    // discarded — while the answer is in flight and, permanently, when it
    // denies write. Pending only picks which reason to show.
    // A placement constraint is a separate verdict and keeps hiding the add
    // button; the permission cases only disable it, so a read-only user still
    // sees the same layout everyone else does.
    const isUnavailable = disabled || isReadOnly;
    const unavailableTooltip = disabled
      ? disabledTooltip
      : isPermissionPending
        ? t("sidebar.permissionsPending")
        : t("sidebar.permissionDenied");

    const version = useDarkStore((state) => state.version);
    const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });
    const popoverRef = useRef<HTMLDivElement>(null);

    const handlePointerDown = (e) => {
      if (!open) {
        const rect = popoverRef.current?.getBoundingClientRect() ?? {
          left: 0,
          top: 0,
        };
        setCursorPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
      }
    };

    function handleSelectChange(value: string) {
      switch (value) {
        case "download": {
          const type = removeCountFromString(itemName);
          downloadNode(
            createFlowComponent(
              { id: getNodeId(type), type, node: apiClass },
              version,
            ),
          );
          break;
        }
        case "delete": {
          if (onDelete) {
            onDelete();
            break;
          }
          const flowId = flows?.find((f) => f.name === display_name);
          if (flowId) deleteFlow({ id: flowId.id });
          break;
        }
      }
    }

    // WCAG 2.5.3 Label in Name (LE-2235): the accessible name must contain
    // the text the row shows, and the Beta / Legacy badge is part of that
    // visible text — so it goes into the name too ("Add Listen Beta to
    // canvas"), otherwise voice-control users saying "click Listen Beta"
    // get no match. Keep these literals in sync with the badges below.
    const visibleName = [display_name, beta && "Beta", legacy && "Legacy"]
      .filter(Boolean)
      .join(" ");
    const addToCanvasLabel = t("sidebar.addComponentToCanvas", {
      name: visibleName,
    });

    const handleKeyDown = (e) => {
      if (isUnavailable) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        addComponent(apiClass, itemName);
      }
    };

    return (
      <Select
        onValueChange={handleSelectChange}
        onOpenChange={(change) => setOpen(change)}
        open={open}
        key={itemName}
      >
        <ShadTooltip
          content={isUnavailable ? unavailableTooltip : null}
          styleClasses="z-50"
        >
          <div
            onPointerDown={handlePointerDown}
            onContextMenuCapture={(e) => {
              e.preventDefault();
              setOpen(true);
            }}
            key={itemName}
            data-tooltip-id={itemName}
            className={cn(
              "group/draggable flex items-center gap-2 rounded-md bg-muted p-1 px-2 hover:bg-secondary-hover/75",
              error && "cursor-not-allowed select-none",
              isUnavailable
                ? "cursor-not-allowed bg-accent text-placeholder-foreground h-8"
                : "bg-muted text-foreground",
            )}
            data-testid={`${sectionName.toLowerCase()}_${display_name.toLowerCase()}_draggable`}
          >
            <div
              data-testid={sectionName + display_name}
              id={sectionName + display_name}
              role="button"
              aria-label={addToCanvasLabel}
              tabIndex={0}
              onKeyDown={handleKeyDown}
              className={cn(
                // `min-w-0` (LE-2311): without it this flex item keeps the
                // default `min-width: auto` and refuses to shrink below the
                // component name's intrinsic width, pushing the sibling
                // add/drag container off the row.
                "flex min-w-0 flex-1 items-center gap-2 rounded-md outline-none ring-ring focus-visible:ring-1",
                isUnavailable ? "cursor-not-allowed" : "cursor-grab",
              )}
              draggable={!error && !isUnavailable}
              style={{
                borderLeftColor: color,
              }}
              onDragStart={onDragStart}
              onDoubleClick={() => {
                if (!isUnavailable) {
                  addComponent(apiClass, itemName);
                }
              }}
              onDragEnd={() => {
                if (
                  document.getElementsByClassName("cursor-grabbing").length > 0
                ) {
                  document.body.removeChild(
                    document.getElementsByClassName("cursor-grabbing")[0],
                  );
                }
              }}
            >
              <ForwardedIconComponent
                name={icon}
                className="h-[18px] w-[18px] shrink-0"
              />
              <div className="flex flex-1 items-center overflow-hidden">
                <ShadTooltip content={display_name} styleClasses="z-50">
                  <span
                    data-testid="display-name"
                    className="truncate text-sm font-normal"
                  >
                    {display_name}
                  </span>
                </ShadTooltip>
                {beta && (
                  <Badge
                    variant="purpleStatic"
                    size="xq"
                    className="ml-1.5 shrink-0"
                  >
                    Beta
                  </Badge>
                )}
                {legacy && (
                  <Badge
                    variant="secondaryStatic"
                    size="xq"
                    className="ml-1.5 shrink-0"
                  >
                    Legacy
                  </Badge>
                )}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {!disabled && (
                <Button
                  data-testid={`add-component-button-${convertTestName(
                    display_name,
                  )}`}
                  variant="ghost"
                  size="icon"
                  tabIndex={-1}
                  disabled={isReadOnly}
                  aria-label={addToCanvasLabel}
                  className="text-primary"
                  onClick={() => addComponent(apiClass, itemName)}
                >
                  <ForwardedIconComponent
                    name="Plus"
                    className="h-4 w-4 shrink-0 transition-all group-hover/draggable:opacity-100 group-focus-within/draggable:opacity-100 sm:opacity-0"
                  />
                </Button>
              )}
              <div ref={popoverRef}>
                <ForwardedIconComponent
                  name="GripVertical"
                  className="h-4 w-4 shrink-0 text-muted-foreground group-hover/draggable:text-primary"
                />
                <SelectTrigger
                  variant="plain"
                  tabIndex={-1}
                  aria-label={t("folder.options")}
                ></SelectTrigger>
                <SelectContent
                  position="popper"
                  side="bottom"
                  sideOffset={-25}
                  className="min-w-[11.5rem]"
                  style={{
                    position: "absolute",
                    left: cursorPos.x,
                    top: cursorPos.y,
                  }}
                >
                  <SelectItem variant="plain" value={"download"}>
                    <div className="flex">
                      <IconComponent
                        name="Download"
                        className="relative top-0.5 mr-2 h-4 w-4"
                      />{" "}
                      {t("sidebar.download")}{" "}
                    </div>{" "}
                  </SelectItem>
                  {(!official || onDelete) && (
                    <SelectItem
                      variant="plain"
                      value={"delete"}
                      data-testid="draggable-component-menu-delete"
                    >
                      <div className="flex">
                        <IconComponent
                          name="Trash2"
                          className="relative top-0.5 mr-2 h-4 w-4"
                        />{" "}
                        {t("sidebar.delete")}{" "}
                      </div>{" "}
                    </SelectItem>
                  )}
                </SelectContent>
              </div>
            </div>
          </div>
        </ShadTooltip>
      </Select>
    );
  },
);

export default SidebarDraggableComponent;
