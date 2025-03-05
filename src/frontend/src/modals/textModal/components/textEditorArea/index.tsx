import { Textarea } from "../../../../components/ui/textarea";

const TextEditorArea = ({
  left,
  value,
  resizable = true,
  onChange,
  readonly,
}: {
  left: boolean | undefined;
  resizable?: boolean;
  value: any;
  onChange?: (string) => void;
  readonly: boolean;
}) => {
  if (typeof value === "object" && Object.keys(value).includes("text")) {
    value = value.text;
  }
  return (
    <Textarea
      readOnly={readonly}
      className={`w-full custom-scroll ${left ? "min-h-32" : "h-full"} ${
        resizable ? "resize-y" : "resize-none"
      }`}
      placeholder={"Empty"}
      // update to real value on flowPool
      value={value}
      onChange={(e) => {
        if (onChange) onChange(e.target.value);
      }}
    />
  );
};

export default TextEditorArea;
