import { useEffect } from "react";
import { FloatComponentType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { Input } from "../ui/input";
import { useTranslation } from "react-i18next";

export default function FloatComponent({
  value,
  onChange,
  disabled,
  rangeSpec,
  editNode = false,
}: FloatComponentType): JSX.Element {
  const { t } = useTranslation();
  const step = rangeSpec?.step ?? 0.1;
  const min = rangeSpec?.min ?? -2;
  const max = rangeSpec?.max ?? 2;
  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("", true);
    }
  }, [disabled]);

  return (
    <div className="w-full">
      <Input
        id="float-input"
        type="number"
        step={step}
        min={min}
        onInput={(event: React.ChangeEvent<HTMLInputElement>) => {
          if (Number(event.target.value) < min) {
            event.target.value = min.toString();
          }
          if (Number(event.target.value) > max) {
            event.target.value = max.toString();
          }
        }}
        max={max}
        value={value ?? ""}
        disabled={disabled}
        className={editNode ? "input-edit-node" : ""}
        placeholder={
          editNode
            ? `${t("Enter a value between")} ${min} ${t("and")} ${max}`
            : `${t("Enter a value between")} ${min} ${t("and")} ${max}`
        }
        onChange={(event) => {
          onChange(event.target.value);
        }}
        onKeyDown={(e) => {
          handleKeyDown(e, value, "");
        }}
      />
    </div>
  );
}
