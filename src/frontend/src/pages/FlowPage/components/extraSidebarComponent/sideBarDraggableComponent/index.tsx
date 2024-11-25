import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import { DragEventHandler, forwardRef, useRef, useState } from "react";
import IconComponent from "../../../../../components/common/genericIconComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "../../../../../components/ui/select-custom";
import { useDarkStore } from "../../../../../stores/darkStore";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import { APIClassType } from "../../../../../types/api";
import {
  createFlowComponent,
  downloadNode,
  getNodeId,
} from "../../../../../utils/reactflowUtils";
import { removeCountFromString } from "../../../../../utils/utils";

export const SidebarDraggableComponent = forwardRef(
  (
    {
      sectionName,
      display_name,
      itemName,
      error,
      color,
      onDragStart,
      apiClass,
      official,
    }: {
      sectionName: string;
      apiClass: APIClassType;
      display_name: string;
      itemName: string;
      error: boolean;
      color: string;
      onDragStart: DragEventHandler<HTMLDivElement>;
      official: boolean;
    },
    ref,
  ) => {
    const [open, setOpen] = useState(false);
    const { deleteFlow } = useDeleteFlow();
    const flows = useFlowsManagerStore((state) => state.flows);

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
        case "share":
          break;
        case "download":
          const type = removeCountFromString(itemName);
          downloadNode(
            createFlowComponent(
              { id: getNodeId(type), type, node: apiClass },
              version,
            ),
          );
          break;
        case "delete":
          const flowId = flows?.find((f) => f.name === display_name);
          if (flowId) deleteFlow({ id: flowId.id });
          break;
      }
    }
    return (
      <Select
        onValueChange={handleSelectChange}
        onOpenChange={(change) => setOpen(change)}
        open={open}
        key={itemName}
      >
        <div
          onPointerDown={handlePointerDown}
          onContextMenuCapture={(e) => {
            e.preventDefault();
            setOpen(true);
          }}
          key={itemName}
          data-tooltip-id={itemName}
        >
          <div
            draggable={!error}
            className={
              "side-bar-components-border bg-background" +
              (error ? " cursor-not-allowed select-none" : "")
            }
            style={{
              borderLeftColor: color,
            }}
            onDragStart={onDragStart}
            onDragEnd={() => {
              document.body.removeChild(
                document.getElementsByClassName("cursor-grabbing")[0],
              );
            }}
          >
            <div
              data-testid={sectionName + display_name}
              id={sectionName + display_name}
              className="side-bar-components-div-form"
            >
              <span className="side-bar-components-text">{display_name}</span>
              <div ref={popoverRef}>
                <IconComponent
                  name="Menu"
                  className="side-bar-components-icon"
                />
                <SelectTrigger></SelectTrigger>
                <SelectContent
                  position="popper"
                  side="bottom"
                  sideOffset={-25}
                  style={{
                    position: "absolute",
                    left: cursorPos.x,
                    top: cursorPos.y,
                  }}
                >
                  <SelectItem value={"download"}>
                    <div className="flex">
                      <IconComponent
                        name="Download"
                        className="relative top-0.5 mr-2 h-4 w-4"
                      />{" "}
                      Download{" "}
                    </div>{" "}
                  </SelectItem>
                  {!official && (
                    <SelectItem value={"delete"}>
                      <div className="flex">
                        <IconComponent
                          name="Trash2"
                          className="relative top-0.5 mr-2 h-4 w-4"
                        />{" "}
                        Delete{" "}
                      </div>{" "}
                    </SelectItem>
                  )}
                </SelectContent>
              </div>
            </div>
          </div>
        </div>
      </Select>
    );
  },
);

export default SidebarDraggableComponent;
