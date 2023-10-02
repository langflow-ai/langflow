import { DragEventHandler } from "react";
import IconComponent from "../../../../../components/genericIconComponent";

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
          <IconComponent name="Menu" className="side-bar-components-icon " />
        </div>
      </div>
    </div>
  );
}
