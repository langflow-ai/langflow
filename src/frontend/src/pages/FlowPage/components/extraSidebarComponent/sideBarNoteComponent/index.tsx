import IconComponent from "../../../../../components/genericIconComponent";
export default function NoteDraggableComponent(){

    function onDragStart(
        event: React.DragEvent<any>,
      ): void {
        event.dataTransfer.setData("note", JSON.stringify({text:null,noteColor:"yellow"}));
      }

    return (
        <div className="cursor-grab" draggable onDragStart={(event)=>onDragStart(event)}>
        <IconComponent name="StickyNote" />
      </div>
    )
}