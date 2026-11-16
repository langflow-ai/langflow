import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import type { InputProps } from "../../types";
import DeleteButtonInputList from "../inputListComponent/components/delete-button-input-list";
import { TimeOfDayField } from "./TimeOfDayField";

type TimeOfDayComponentType = {
  /** Several times with an "Add time" button, or a single time. */
  list?: boolean;
  componentName?: string;
};

const asTimes = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.map(String);
  return typeof value === "string" && value ? [value] : [];
};

/** One time of day, or a list of them, in the reader's clock format. */
export default function TimeOfDayComponent({
  id,
  value,
  handleOnNewValue,
  disabled,
  editNode = false,
  list = false,
  componentName = "",
  ariaLabelledBy,
}: InputProps<string[] | string, TimeOfDayComponentType>): JSX.Element {
  const { t } = useTranslation();

  if (!list) {
    return (
      <TimeOfDayField
        value={typeof value === "string" ? value : (asTimes(value)[0] ?? "")}
        onChange={(time) => handleOnNewValue({ value: time })}
        disabled={disabled}
        editNode={editNode}
        dataTestId={id}
        ariaLabelledBy={ariaLabelledBy}
      />
    );
  }

  const times = asTimes(value);
  const rows = times.length > 0 ? times : [""];
  const save = (next: string[]) => handleOnNewValue({ value: next });

  return (
    <div className="flex w-full flex-col gap-2">
      {rows.map((time, index) => (
        <div key={index} className="flex w-full items-start gap-2">
          <TimeOfDayField
            value={time}
            onChange={(next) =>
              save(rows.map((row, at) => (at === index ? next : row)))
            }
            disabled={disabled}
            editNode={editNode}
            dataTestId={`${id}_${index}`}
            ariaLabelledBy={index === 0 ? ariaLabelledBy : undefined}
            ariaLabel={
              index === 0 ? undefined : t("timeOfDay.nth", { n: index + 1 })
            }
          />
          {rows.length > 1 && (
            <div className="pt-2.5">
              <DeleteButtonInputList
                index={index}
                removeInput={(event) => {
                  event.preventDefault();
                  save(rows.filter((_row, at) => at !== index));
                }}
                disabled={Boolean(disabled)}
                editNode={editNode}
                componentName={componentName}
              />
            </div>
          )}
        </div>
      ))}
      {!disabled && (
        <Button
          unstyled
          type="button"
          onClick={() => save([...rows, ""])}
          className="btn-add-input-list"
          data-testid={`${id}_add`}
        >
          <IconComponent name="Plus" className="mr-1 h-4 w-4" />
          {t("timeOfDay.add")}
        </Button>
      )}
    </div>
  );
}
