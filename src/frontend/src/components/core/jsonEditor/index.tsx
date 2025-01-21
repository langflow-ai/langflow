import { useEffect, useRef } from "react";
import {
  Content,
  createJSONEditor,
  JsonEditor as VanillaJsonEditor,
} from "vanilla-jsoneditor";

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

    return () => {
      if (newRef.current) {
        newRef.current.destroy();
      }
    };
  }, []);

  return (
    <div ref={containerRef} style={{ width, height }} className={className} />
  );
};

export default JsonEditor;
