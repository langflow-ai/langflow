import { KeyboardEvent, useEffect, useRef, useState } from "react";
import {
  Content,
  createJSONEditor,
  JsonEditor as VanillaJsonEditor,
} from "vanilla-jsoneditor";
import { Button } from "../../ui/button";
import { Input } from "../../ui/input";
import useAlertStore from "../../../stores/alertStore";

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
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const handleTransform = () => {
    if (!newRef.current) return;

    // If query is empty, act as reset
    if (!transformQuery.trim()) {
      handleReset();
      return;
    }

    try {
      const content = newRef.current.get();
      const json = "json" in content ? content.json : JSON.parse(content.text!);

      // Convert jQuery-style path to nested property access
      const path = transformQuery.trim().split(".").filter(Boolean);
      let result = json;

      for (const key of path) {
        if (result === undefined || result === null) {
          setErrorData({
            title: "Invalid Path",
            list: [`Path '${transformQuery}' led to undefined or null value`]
          });
          return;
        }
        if (Array.isArray(result)) {
          // Handle array access with [index] notation
          const indexMatch = key.match(/\[(\d+)\]/);
          if (indexMatch) {
            const index = parseInt(indexMatch[1]);
            if (index >= result.length) {
              setErrorData({
                title: "Invalid Array Index",
                list: [`Index ${index} is out of bounds for array of length ${result.length}`]
              });
              return;
            }
            result = result[index];
            continue;
          }
          // Apply operation to all array items
          result = result.map(item => {
            if (!(key in item)) {
              setErrorData({
                title: "Invalid Property",
                list: [`Property '${key}' does not exist in array items`]
              });
              return undefined;
            }
            return item[key];
          }).filter(item => item !== undefined);
        } else {
          if (!(key in result)) {
            setErrorData({
              title: "Invalid Property",
              list: [`Property '${key}' does not exist in object`]
            });
            return;
          }
          result = result[key];
        }
      }

      if (result !== undefined) {
        newRef.current.set({ json: result });
        onChange?.({ json: result });
      } else {
        setErrorData({
          title: "Invalid Result",
          list: ["Transform resulted in undefined value"]
        });
      }
    } catch (error) {
      console.error('Error applying transform:', error);
      setErrorData({
        title: "Transform Error",
        list: [(error as Error).message]
      });
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
        readOnly,

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
          variant="primary"
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
