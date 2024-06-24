import { Textarea } from "../../../../components/ui/textarea";
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();
  return (
    <Textarea
      readOnly={readonly}
      className={`w-full custom-scroll ${left ? "min-h-32" : "h-full"}`}
      placeholder={t("Empty")}
      // update to real value on flowPool
      value={value}
      onChange={(e) => {
        if (onChange) onChange(e.target.value);
      }}
    />
  );
};

export default TextEditorArea;
