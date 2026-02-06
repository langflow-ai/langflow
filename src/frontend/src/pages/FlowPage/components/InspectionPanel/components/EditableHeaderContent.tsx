import { useEffect, useRef, useState, useCallback, memo, useMemo } from "react";
import Markdown from "react-markdown";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { NodeDataType } from "@/types/flow";
import { cn } from "@/utils/utils";

interface EditableHeaderContentProps {
  data: NodeDataType;
  editMode: boolean;
  setEditMode: (value: boolean) => void;
}

export default function EditableHeaderContent({
  data,
  editMode,
  setEditMode,
}: EditableHeaderContentProps) {
  const [localName, setLocalName] = useState<string>(
    data.node?.display_name ?? data.type,
  );
  const [localDescription, setLocalDescription] = useState<string>(
    data.node?.description ?? "",
  );

  const takeSnapshot = useFlowsManagerStore((state) => state.takeSnapshot);
  const setNode = useFlowStore((state) => state.setNode);

  const nameInputRef = useRef<HTMLInputElement>(null);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hasChangedRef = useRef(false);

  // Update local state when data changes
  useEffect(() => {
    setLocalName(data.node?.display_name ?? data.type);
    setLocalDescription(data.node?.description ?? "");
  }, [data.node?.display_name, data.node?.description, data.type]);

  const handleSave = useCallback(() => {
    if (!hasChangedRef.current) return;

    const trimmedName = localName.trim();
    const finalName =
      trimmedName !== "" ? trimmedName : (data.node?.display_name ?? data.type);

    setNode(data.id, (old) => ({
      ...old,
      data: {
        ...old.data,
        node: {
          ...old.data.node,
          display_name: finalName,
          description: localDescription,
        },
      },
    }));

    hasChangedRef.current = false;
  }, [
    localName,
    localDescription,
    data.id,
    data.node?.display_name,
    data.type,
    setNode,
  ]);

  // Take snapshot when entering edit mode
  useEffect(() => {
    if (editMode) {
      takeSnapshot();
      hasChangedRef.current = false;
      // Auto-focus name input when entering edit mode
      setTimeout(() => {
        nameInputRef.current?.focus();
        // Auto-size description textarea
        if (descriptionRef.current) {
          descriptionRef.current.style.height = "auto";
          descriptionRef.current.style.height =
            descriptionRef.current.scrollHeight + "px";
        }
      }, 0);
    }
  }, [editMode, takeSnapshot]);

  // Handle click outside to save and exit edit mode
  useEffect(() => {
    if (!editMode) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;

      // Check if click is outside the container
      if (containerRef.current && !containerRef.current.contains(target)) {
        handleSave();
        setEditMode(false);
      }
    };

    // Add listener with a small delay to avoid immediate trigger
    const timeoutId = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [editMode, setEditMode, handleSave]);

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalName(e.target.value);
    hasChangedRef.current = true;
  };

  const handleDescriptionChange = (
    e: React.ChangeEvent<HTMLTextAreaElement>,
  ) => {
    setLocalDescription(e.target.value);
    hasChangedRef.current = true;

    // Auto-grow textarea
    e.target.style.height = "auto";
    e.target.style.height = e.target.scrollHeight + "px";
  };

  const handleNameKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      // Save and exit edit mode
      handleSave();
      setEditMode(false);
    }
    if (e.key === "Escape") {
      setLocalName(data.node?.display_name ?? data.type);
      setLocalDescription(data.node?.description ?? "");
      hasChangedRef.current = false;
      nameInputRef.current?.blur();
      setEditMode(false);
    }
  };

  const handleDescriptionKeyDown = (
    e: React.KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (e.key === "Escape") {
      setLocalName(data.node?.display_name ?? data.type);
      setLocalDescription(data.node?.description ?? "");
      hasChangedRef.current = false;
      e.currentTarget.blur();
      setEditMode(false);
    }
  };

  const MemoizedMarkdown = memo(Markdown);

  const renderedDescription = useMemo(() => {
    const description = data.node?.description;
    if (description === "" || !description) {
      return "";
    }
    return (
      <div className="mt-1">
        <MemoizedMarkdown
          className={cn(
            "markdown prose !text-muted-foreground flex w-full flex-col text-xs leading-5 word-break-break-word [&_pre]:whitespace-break-spaces [&_pre]:!bg-code-description-background [&_pre_code]:!bg-code-description-background dark:prose-invert",
          )}
          components={{
            a: ({ node, ...props }) => (
              <a {...props} target="_blank" rel="noopener noreferrer">
                {props.children}
              </a>
            ),
          }}
        >
          {String(description)}
        </MemoizedMarkdown>
      </div>
    );
  }, [data.node?.description, editMode]);

  return {
    containerRef,
    handleSave,
    nameElement: editMode ? (
      <Input
        ref={nameInputRef}
        value={localName}
        onChange={handleNameChange}
        onKeyDown={handleNameKeyDown}
        className="px-2 py-0 font-medium text-sm"
        data-testid="inspection-panel-name"
      />
    ) : (
      <span className="font-medium text-sm">
        {data.node?.display_name ?? data.type}
      </span>
    ),
    descriptionElement: editMode ? (
      <Textarea
        ref={descriptionRef}
        value={localDescription}
        onChange={handleDescriptionChange}
        onKeyDown={handleDescriptionKeyDown}
        className="nowheel w-full mt-1 text-muted-foreground !text-xs focus:border-primary focus:ring-0 px-2 py-0.5 min-h-[60px]"
        placeholder="Add a description..."
        data-testid="inspection-panel-description"
      />
    ) : (
      renderedDescription
    ),
  };
}
