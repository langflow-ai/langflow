import { useEffect, useRef } from "react";
import {
  Content,
  createJSONEditor,
  JsonEditor as VanillaJsonEditor,
} from "vanilla-jsoneditor";

interface JsonEditorProps {
  data?: Content;
  onChange?: (data: Content) => void;
  options?: any;
  jsonRef?: React.MutableRefObject<VanillaJsonEditor | null>;
  width?: string;
  height?: string;
}

const JsonEditor = ({
  data = { json: {} },
  onChange,
  jsonRef,
  options = {},
  width = "100%",
  height = "400px",
}: JsonEditorProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const jsonEditorRef = useRef<VanillaJsonEditor | null>(null);
  const newRef = jsonRef ?? jsonEditorRef;

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

    return () => {
      if (newRef.current) {
        newRef.current.destroy();
      }
    };
  }, []);

  return <div ref={containerRef} style={{ width, height }} />;
};

export default JsonEditor;
