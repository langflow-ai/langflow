import JsonEditor from "@/components/core/jsonEditor";
import type { IOJSONInputComponentType } from "@/types/components";
import { useEffect, useRef } from "react";
import type { JsonEditor as VanillaJsonEditor } from "vanilla-jsoneditor";
export default function IoJsonInput({
  value = [],
  onChange,
  left,
  output,
}: IOJSONInputComponentType): JSX.Element {
  const ref = useRef<any>(null);
  ref.current = value;

  const jsonEditorRef = useRef<VanillaJsonEditor | null>(null);

  useEffect(() => {
    if (jsonEditorRef.current) {
      jsonEditorRef.current.set({ json: value || {} });
    }
  }, [value]);

  return (
    <div className="h-400px w-full">
      <JsonEditor
        data={{ json: value }}
        jsonRef={jsonEditorRef}
        height="400px"
      />
    </div>
  );
}
