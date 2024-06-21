import { Textarea } from "../../../../components/ui/textarea";

const TextEditorArea = ({
  left,
  value,
  onChange,
  readonly,
}: {
  left: boolean | undefined;
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
      className={`w-full custom-scroll ${left ? "min-h-32" : "h-full"}`}
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
