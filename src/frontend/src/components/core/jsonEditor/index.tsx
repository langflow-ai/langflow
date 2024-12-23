import JSONEditor from "jsoneditor";
import "jsoneditor/dist/img/jsoneditor-icons.svg";
import "jsoneditor/dist/jsoneditor.css";
import "jsoneditor/dist/jsoneditor.min.css";
import { useEffect, useRef } from "react";

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
  const jsonEditorRef = useRef<JSONEditor | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Initialize the editor
    const editor = new JSONEditor(containerRef.current, {
      ...options,
      onChange: () => {
        try {
          const updatedData = editor.get();
          onChange?.(updatedData);
        } catch (error) {
          console.error("Error getting JSON:", error);
        }
      },
    });

    // Set initial data
    editor.set(data);

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
      jsonEditorRef.current.update(data);
    }
  }, [data]);

  return <div ref={containerRef} style={{ width, height }} />;
};

export default JsonEditor;
