import type { FlowType } from "@/types/flow";
import { useCallback } from "react";
import { createRoot } from "react-dom/client";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import DragCardComponent from "../components/dragCardComponent";

const useDragStart = (data: FlowType) => {
  const getFlowById = useFlowsManagerStore((state) => state.getFlowById);

  const onDragStart = useCallback(
    (event) => {
      const image = <DragCardComponent data={data} />; // Replace with whatever you want here

      const ghost = document.createElement("div");
      ghost.style.transform = "translate(-10000px, -10000px)";
      ghost.style.position = "absolute";
      document.body.appendChild(ghost);
      event.dataTransfer.setDragImage(ghost, 0, 0);

      const root = createRoot(ghost);
      root.render(image);

      const flow = getFlowById(data.id);
      if (flow) {
        event.dataTransfer.setData("flow", JSON.stringify(data));
      }
    },
    [data],
  );

  return { onDragStart };
};

export default useDragStart;
