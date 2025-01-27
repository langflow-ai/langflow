import { KeyboardEvent, useEffect, useRef, useState } from "react";
import {
  Content,
  createJSONEditor,
  JsonEditor as VanillaJsonEditor,
} from "vanilla-jsoneditor";
import { Button } from "../../ui/button";
import { Input } from "../../ui/input";

interface JsonEditorProps {
  data?: Content;
  onChange?: (data: Content) => void;
  readOnly?: boolean;
  options?: any;
  jsonRef?: React.MutableRefObject<VanillaJsonEditor | null>;
  width?: string;
  height?: string;
  className?: string;
}

const JsonEditor = ({
  data = { json: {} },
  onChange,
  readOnly,
  jsonRef,
  options = {},
  width = "100%",
  height = "400px",
  className,
}: JsonEditorProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const jsonEditorRef = useRef<VanillaJsonEditor | null>(null);
  const newRef = jsonRef ?? jsonEditorRef;
  const [transformQuery, setTransformQuery] = useState("");
  const [originalData, setOriginalData] = useState(data);

  const handleTransform = () => {
    if (!transformQuery.trim() || !newRef.current) return;

    try {
      const content = newRef.current.get();
      const json = "json" in content ? content.json : JSON.parse(content.text!);

      // Convert jQuery-style path to nested property access
      const path = transformQuery.trim().split(".").filter(Boolean);
      let result = json;

      for (const key of path) {
        if (result === undefined || result === null) break;
        if (Array.isArray(result)) {
          // Handle array access with [index] notation
          const indexMatch = key.match(/\[(\d+)\]/);
          if (indexMatch) {
            result = result[parseInt(indexMatch[1])];
            continue;
          }
          // Apply operation to all array items
          result = result.map((item) => item[key]);
        } else {
          result = result[key];
        }
      }

      if (result !== undefined) {
        newRef.current.set({ json: result });
        onChange?.({ json: result });
        setTransformQuery("");
      }
    } catch (error) {
      console.error("Error applying transform:", error);
    }
  };

  const handleReset = () => {
    if (!newRef.current) return;
    newRef.current.set(originalData);
    onChange?.(originalData);
    setTransformQuery("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleTransform();
    }
  };

  useEffect(() => {
    if (!containerRef.current) return;

    const editor = createJSONEditor({
      target: containerRef.current,
      props: {
        ...options,
        navigationBar: false,
        mode: "text",
        content: data,

        onChange: (content) => {
          onChange?.(content);
        },
      },
    });

    setTimeout(() => editor.focus(), 100);

    newRef.current = editor;
    setOriginalData(data);

    return () => {
      if (newRef.current) {
        newRef.current.destroy();
      }
    };
  }, []);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <Input
          placeholder="Enter path (e.g. users[0].name or results.data)"
          value={transformQuery}
          onChange={(e) => setTransformQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          className="font-mono text-sm"
        />
        <Button
          onClick={handleTransform}
          variant="secondary"
          size="sm"
          className="whitespace-nowrap"
        >
          Filter
        </Button>
        <Button
          onClick={handleReset}
          variant="outline"
          size="sm"
          className="whitespace-nowrap"
        >
          Reset
        </Button>
      </div>
      <div ref={containerRef} style={{ width, height }} className={className} />
    </div>
  );
};

export default JsonEditor;
