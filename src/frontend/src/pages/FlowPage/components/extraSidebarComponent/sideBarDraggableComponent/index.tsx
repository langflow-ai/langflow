import { DragEventHandler, useRef, useState } from "react";
import IconComponent from "../../../../../components/genericIconComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "../../../../../components/ui/select-custom";

export default function SidebarDraggableComponent({
  display_name,
  itemName,
  error,
  color,
  onDragStart,
}: {
  display_name: string;
  itemName: string;
  error: boolean;
  color: string;
  onDragStart: DragEventHandler<HTMLDivElement>;
}) {
  const isOpen = useRef(false);
  const [editMode, setEditMode] = useState(false);
  const inside = useRef(false);

  return (
    <div key={itemName} data-tooltip-id={itemName}>
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
            document.getElementsByClassName("cursor-grabbing")[0]
          );
        }}
      >
        <div className="side-bar-components-div-form">
          <span className="side-bar-components-text">{display_name}</span>
          <div
            onMouseLeave={() => {
              if (!isOpen.current) {
                inside.current = false;
                setEditMode(false);
              }
            }}
            onMouseOver={() => {
              inside.current = true;
              setTimeout(() => {
                if (inside.current) setEditMode(true);
              }, 800);
            }}
          >
            {editMode ? (
              <Select
                onOpenChange={(open) => {
                  if (!open) {
                    isOpen.current = false;
                    inside.current = false;
                    setEditMode(false);
                  } else {
                    isOpen.current = true;
                  }
                }}
              >
                <SelectTrigger>
                  <IconComponent
                    name="MoreHorizontal"
                    className="side-bar-components-icon "
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={"share"}>
                    <div className="flex">
                      <IconComponent
                        name="Share2"
                        className="relative top-0.5 mr-2 h-4 w-4"
                      />{" "}
                      Share{" "}
                    </div>{" "}
                  </SelectItem>
                  <SelectItem value={"download"}>
                    <div className="flex">
                      <IconComponent
                        name="Download"
                        className="relative top-0.5 mr-2 h-4 w-4"
                      />{" "}
                      Download{" "}
                    </div>{" "}
                  </SelectItem>
                  <SelectItem value={"delete"}>
                    <div className="flex">
                      <IconComponent
                        name="Trash2"
                        className="relative top-0.5 mr-2 h-4 w-4"
                      />{" "}
                      Delete{" "}
                    </div>{" "}
                  </SelectItem>
                </SelectContent>
              </Select>
            ) : (
              <IconComponent
                name="Menu"
                className="side-bar-components-icon "
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
