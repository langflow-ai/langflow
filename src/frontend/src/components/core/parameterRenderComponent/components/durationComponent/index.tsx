import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import { testIdCase } from "@/utils/utils";
import type { InputProps, TabComponentType } from "../../types";

type DurationValue = { value: number; unit: string };

export default function DurationComponent({
  id,
  value,
  options = [],
  handleOnNewValue,
  disabled,
}: InputProps<DurationValue, TabComponentType>): JSX.Element {
  const units = options.length > 0 ? options : ["Minutes", "Hours", "Days"];
  const current: DurationValue =
    value && typeof value === "object"
      ? value
      : { value: 0, unit: units[units.length - 1] };

  const update = (patch: Partial<DurationValue>) =>
    handleOnNewValue({ value: { ...current, ...patch } });

  return (
    <div className="flex w-full items-center gap-2">
      <Input
        type="number"
        min={0}
        disabled={disabled}
        value={String(current.value ?? 0)}
        onChange={(event) => update({ value: Number(event.target.value) || 0 })}
        data-testid={`duration-value-${id}`}
        className="w-20 shrink-0"
      />
      <Tabs
        value={current.unit}
        onValueChange={(unit) => update({ unit })}
        className={`flex-1 ${disabled ? "pointer-events-none opacity-70" : ""}`}
      >
        <TabsList className="w-full">
          {units.map((unit, index) => (
            <TabsTrigger
              key={`${id}_unit_${unit}`}
              value={unit}
              className="block flex-1 truncate px-2"
              disabled={disabled}
              data-testid={`duration-unit-${index}_${testIdCase(unit)}`}
            >
              {unit}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  );
}
