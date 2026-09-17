import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function ProjectChoiceField({
  name,
  label,
  options,
  value,
  disabled,
  onChange,
}: {
  name: string;
  label: string;
  options: Record<string, string>;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <Select value={value} disabled={disabled} onValueChange={onChange}>
      <SelectTrigger aria-label={label} data-testid={`harness-choice-${name}`}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {Object.entries(options).map(([key, text]) => (
          <SelectItem key={key} value={key}>
            {text}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
