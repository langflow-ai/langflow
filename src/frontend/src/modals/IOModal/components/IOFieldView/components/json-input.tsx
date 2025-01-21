import { IOJSONInputComponentType } from "@/types/components";
import { useEffect, useRef } from "react";
import { JsonEditor as VanillaJsonEditor } from "vanilla-jsoneditor";
import JsonEditor from "@/components/core/jsonEditor";
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
    <div className="w-full h-400px">
      <JsonEditor
        data={{ json: value }}
        jsonRef={jsonEditorRef}
        height="400px"
      />
    </div>
  );
}
