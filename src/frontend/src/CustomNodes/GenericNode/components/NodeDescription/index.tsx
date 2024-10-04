import { Textarea } from "@/components/ui/textarea";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { handleKeyDown } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";

export default function NodeDescription({
  description,
  selected,
  nodeId,
  emptyPlaceholder = "Double Click to Edit Description",
  charLimit,
  inputClassName,
  mdClassName,
  style,
}: {
  description?: string;
  selected: boolean;
  nodeId: string;
  emptyPlaceholder?: string;
  charLimit?: number;
  inputClassName?: string;
  mdClassName?: string;
  style?: React.CSSProperties;
}) {
  const [inputDescription, setInputDescription] = useState(false);
  const [nodeDescription, setNodeDescription] = useState(description);
  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const setNode = useFlowStore((state) => state.setNode);
  const overflowRef = useRef<HTMLDivElement>(null);
  const [hasScroll, sethasScroll] = useState(false);

  useEffect(() => {
    //timeout to wait for the dom to update
    setTimeout(() => {
      if (overflowRef.current) {
        if (
          overflowRef.current.clientHeight < overflowRef.current.scrollHeight
        ) {
          sethasScroll(true);
        } else {
          sethasScroll(false);
        }
      }
    }, 200);
  }, [inputDescription]);

  useEffect(() => {
    if (!selected) {
      setInputDescription(false);
    }
  }, [selected]);

  useEffect(() => {
    setNodeDescription(description);
  }, [description]);

  return (
    <div
      className={cn(
        "generic-node-desc",
        !inputDescription ? "overflow-auto" : "",
        hasScroll ? "nowheel" : "",
        charLimit ? "px-2" : "",
      )}
    >
      {inputDescription ? (
        <>
          <Textarea
            maxLength={charLimit}
            className={cn("nowheel h-full", inputClassName)}
            autoFocus
            style={style}
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
          {charLimit && (
            <div
              className={cn(
                "text-left text-xs",
                (nodeDescription?.length ?? 0) >= charLimit
                  ? "text-error"
                  : "text-primary",
              )}
              data-testid="note_char_limit"
            >
              {nodeDescription?.length ?? 0}/{charLimit}
            </div>
          )}
        </>
      ) : (
        <div
          ref={overflowRef}
          className={cn(
            "nodoubleclick generic-node-desc-text h-full cursor-text word-break-break-word dark:text-note-placeholder",
            description === "" || !description ? "font-light italic" : "",
          )}
          onDoubleClick={(e) => {
            setInputDescription(true);
            takeSnapshot();
          }}
        >
          {description === "" || !description ? (
            emptyPlaceholder
          ) : (
            <Markdown
              className={cn(
                "markdown prose flex h-full w-full flex-col text-primary word-break-break-word note-node-markdown dark:prose-invert",
                mdClassName,
              )}
            >
              {String(description)}
            </Markdown>
          )}
        </div>
      )}
    </div>
  );
}
