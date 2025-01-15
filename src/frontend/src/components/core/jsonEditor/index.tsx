import { useDarkStore } from "@/stores/darkStore";
import { useEffect, useRef } from "react";
import {
  Content,
  createJSONEditor,
  JsonEditor as VanillaJsonEditor,
} from "vanilla-jsoneditor";

interface JsonEditorProps {
  data?: object;
  onChange?: (data: object) => void;
  options?: any;
  width?: string;
  height?: string;
}

const JsonEditor = ({
  data = {},
  onChange,
  options = {},
  width = "100%",
  height = "400px",
}: JsonEditorProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const jsonEditorRef = useRef<VanillaJsonEditor | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Initialize the editor with proper types
    const editor = createJSONEditor({
      target: containerRef.current,
      props: {
        ...options,
        content: data,

        onChange: () => {
          try {
            const content = editor.get();
            // Extract the json value from the content
            const jsonValue = (content as { json: object }).json;
            onChange?.(jsonValue);
          } catch (error) {
            console.error("Error getting JSON:", error);
          }
        },
      },
    });

    // Store editor instance
    jsonEditorRef.current = editor;

    // Cleanup
    return () => {
      if (jsonEditorRef.current) {
        jsonEditorRef.current.destroy();
      }
    };
  }, []); // Empty dependency array since we only want to initialize once

  // Update data when prop changes
  useEffect(() => {
    if (jsonEditorRef.current) {
      jsonEditorRef.current.set({ json: data } as Content);
    }
  }, [data]);

  const dark = useDarkStore((state) => state.dark);

  return <div ref={containerRef} style={{ width, height }} />;
};

export default JsonEditor;
