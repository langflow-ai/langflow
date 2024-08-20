import { useEffect, useRef, useState } from "react";
import { NodeResizeControl } from "reactflow";
import { cn } from "../../utils/utils";
import { noteDataType } from "@/types/flow";
import IconComponent from "../../components/genericIconComponent";
import NodeName from "../GenericNode/components/NodeName";

function NoteNode({ data, selected }:{data: noteDataType, selected: boolean}) {

  return (
    <>
      <div className="generic-node-div">
        <div className="flex w-full">
          <IconComponent name="StickyNote"/>
          <NodeName nodeId={data.id} selected={selected} display_name={data.node?.display_name??"Note"}/>
        </div>
      </div>
    </>
  );
}

export default NoteNode;