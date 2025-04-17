import { APIClassType } from "@/types/api";
import IconComponent from "../../../../../components/common/genericIconComponent";
export default function NoteDraggableComponent() {
  function onDragStart(event: React.DragEvent<any>): void {
    const noteNode: APIClassType = {
      description: "",
      display_name: "",
      documentation: "",
      template: {},
    };
    event.dataTransfer.setData(
      "noteNode",
      JSON.stringify({ node: noteNode, type: "note" }),
    );
  }

  return (
    <div
      draggable
      className={"bg-background cursor-grab rounded-l-md p-2"}
      onDragStart={onDragStart}
    >
      <div
        data-testid={"note_component"}
        id={"note component"}
        className="border-ring flex w-full items-center justify-between rounded-md border border-dashed px-3 py-1 text-sm"
      >
        <IconComponent name="StickyNote" className="pr-2" />
        <span className="side-bar-components-text">Add Note</span>
        <IconComponent name="Menu" className="side-bar-components-icon" />
      </div>
    </div>
  );
}
