import { Textarea } from "@/components/ui/textarea";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { handleKeyDown } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";

export default function NodeDescription({
  description,
  selected,
  nodeId,
  emptyPlaceholder = "Double Click to Edit Description",
  placeholderClassName,
  charLimit,
  inputClassName,
  mdClassName,
  style,
}: {
  description?: string;
  selected: boolean;
  nodeId: string;
  emptyPlaceholder?: string;
  placeholderClassName?: string;
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

  const MemoizedMarkdown = memo(Markdown);
  const renderedDescription = useMemo(
    () =>
      description === "" || !description ? (
        emptyPlaceholder
      ) : (
        <MemoizedMarkdown
          linkTarget="_blank"
          className={cn(
            "markdown prose flex w-full flex-col text-[13px] leading-5 word-break-break-word [&_pre]:whitespace-break-spaces [&_pre]:!bg-code-description-background [&_pre_code]:!bg-code-description-background",
            mdClassName,
          )}
        >
          {String(description)}
        </MemoizedMarkdown>
      ),
    [description, emptyPlaceholder, mdClassName],
  );

  return (
    <div
      className={cn(
        !inputDescription ? "overflow-auto" : "",
        hasScroll ? "nowheel" : "",
        charLimit ? "px-2 pb-4" : "",
        "w-full",
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
              if (e.key === "Escape") {
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
          {charLimit && (nodeDescription?.length ?? 0) >= charLimit - 100 && (
            <div
              className={cn(
                "pt-1 text-left text-[13px]",
                (nodeDescription?.length ?? 0) >= charLimit
                  ? "text-error"
                  : "text-primary",
                placeholderClassName,
              )}
              data-testid="note_char_limit"
            >
              {nodeDescription?.length ?? 0}/{charLimit}
            </div>
          )}
        </>
      ) : (
        <div
          data-testid="generic-node-desc"
          ref={overflowRef}
          className={cn(
            "nodoubleclick generic-node-desc-text h-full cursor-text text-[13px] text-muted-foreground word-break-break-word",
            description === "" || !description ? "font-light italic" : "",
            placeholderClassName,
          )}
          onDoubleClick={(e) => {
            setInputDescription(true);
            takeSnapshot();
          }}
        >
          {renderedDescription}
        </div>
      )}
    </div>
  );
}
