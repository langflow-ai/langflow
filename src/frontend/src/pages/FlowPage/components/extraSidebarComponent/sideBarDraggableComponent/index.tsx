import { DragEventHandler, useContext, useRef } from "react";
import IconComponent from "../../../../../components/genericIconComponent";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "../../../../../components/ui/select-custom";
import { typesContext } from "../../../../../contexts/typesContext";

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
  const open = useRef(false);
  const { deleteComponent } = useContext(typesContext);

  function handleSelectChange(value: string) {
    switch (value) {
      case "share":
        break;
      case "download":
        break;
      case "delete":
        deleteComponent(itemName);
        break;
    }
  }

  return (
    <Select
      onValueChange={handleSelectChange}
      onOpenChange={(change) => (open.current = change)}
      open={open.current}
    >
      <div
        onContextMenuCapture={(e) => {
          e.preventDefault();
          open.current = true;
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
              document.getElementsByClassName("cursor-grabbing")[0]
            );
          }}
        >
          <div className="side-bar-components-div-form">
            <span className="side-bar-components-text">{display_name}</span>
            <div>
              <SelectTrigger>
                <IconComponent
                  name="Menu"
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
            </div>
          </div>
        </div>
      </div>
    </Select>
  );
}
