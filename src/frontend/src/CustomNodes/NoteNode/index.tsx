
import { noteDataType } from "@/types/flow";
import IconComponent from "../../components/genericIconComponent";
import NodeName from "../GenericNode/components/NodeName";
import NodeDescription from "../GenericNode/components/NodeDescription";

function NoteNode({ data, selected }:{data: noteDataType, selected: boolean}) {

  return (
    <>
      <div className="generic-node-div">
        <div className="flex w-18">
          <IconComponent name="StickyNote"/>
          <NodeName nodeId={data.id} selected={selected} display_name={data.node?.display_name||"Note"}/>
        </div>
        <NodeDescription nodeId={data.id} selected={selected} description={data.node?.description} emptyPlaceholder="Double Click to Edit Note"
          />
      </div>
    </>
  );
}

export default NoteNode;