import { IOJSONInputComponentType } from "@/types/components";
import { useEffect, useRef } from "react";
import JsonView from "react18-json-view";
import { useDarkStore } from "../../../../../../stores/darkStore";

export default function IoJsonInput({
  value = [],
  onChange,
  left,
  output,
}: IOJSONInputComponentType): JSX.Element {
  useEffect(() => {
    if (value) onChange(value);
  }, [value]);
  const isDark = useDarkStore((state) => state.dark);

  const ref = useRef<any>(null);
  ref.current = value;

  const getClassNames = () => {
    if (!isDark && !left) return "json-view-playground-white";
    if (!isDark && left) return "json-view-playground-white-left";
    if (isDark && left) return "json-view-playground-dark-left";
    if (isDark && !left) return "json-view-playground-dark";
  };

  return (
    <div className="w-full">
      <JsonView
        className={getClassNames()}
        theme="vscode"
        dark={isDark}
        editable={!output}
        enableClipboard
        onEdit={(edit) => {
          ref.current = edit["src"];
        }}
        onChange={(edit) => {
          ref.current = edit["src"];
        }}
        src={ref.current}
      />
    </div>
  );
}
