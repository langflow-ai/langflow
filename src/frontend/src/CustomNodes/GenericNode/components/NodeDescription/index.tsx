import { Textarea } from "@/components/ui/textarea";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { handleKeyDown } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import { useEffect, useState } from "react";
import Markdown from "react-markdown";

export default function NodeDescription({
  description,
  selected,
  nodeId,
}: {
  description?: string;
  selected: boolean;
  nodeId: string;
}) {
  const [inputDescription, setInputDescription] = useState(false);
  const [nodeDescription, setNodeDescription] = useState(description);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const setNode = useFlowStore((state) => state.setNode);

  useEffect(() => {
    if (!selected) {
      setInputDescription(false);
    }
  }, [selected]);

  useEffect(() => {
    setNodeDescription(description);
  }, [description]);

  return (
    <div className="generic-node-desc">
      {inputDescription ? (
        <Textarea
          className="nowheel min-h-40"
          autoFocus
          onBlur={() => {
            setInputDescription(false);
            setNodeDescription(nodeDescription);
            setNode(nodeId, (old) => ({
              ...old,
              data: {
                ...old.data,
                node: {
                  ...old.data.node,
                  description: nodeDescription,
                },
              },
            }));
          }}
          value={nodeDescription}
          onChange={(e) => setNodeDescription(e.target.value)}
          onKeyDown={(e) => {
            handleKeyDown(e, nodeDescription, "");
            if (
              e.key === "Enter" &&
              e.shiftKey === false &&
              e.ctrlKey === false &&
              e.altKey === false
            ) {
              setInputDescription(false);
              setNodeDescription(nodeDescription);
              setNode(nodeId, (old) => ({
                ...old,
                data: {
                  ...old.data,
                  node: {
                    ...old.data.node,
                    description: nodeDescription,
                  },
                },
              }));
            }
          }}
        />
      ) : (
        <div
          className={cn(
            "nodoubleclick generic-node-desc-text cursor-text word-break-break-word",
            description === "" || !description ? "font-light italic" : "",
          )}
          onDoubleClick={(e) => {
            setInputDescription(true);
            takeSnapshot();
          }}
        >
          {description === "" || !description ? (
            "Double Click to Edit Description"
          ) : (
            <Markdown className="markdown prose flex flex-col text-primary word-break-break-word dark:prose-invert">
              {String(description)}
            </Markdown>
          )}
        </div>
      )}
    </div>
  );
}
