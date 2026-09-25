import { Textarea } from "@/components/ui/textarea";

interface LongTextFieldProps {
  name: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}

/**
 * A full-height editor for a field meant to be written, not filled in.
 *
 * The canvas renders a multiline input as one line plus a button that opens a modal, which is
 * right for a node 200px wide and wrong for the main field of a page. A project type asks for
 * this one by name (`renders: "long_text"`).
 */
export const LongTextField = ({
  name,
  value,
  placeholder,
  onChange,
}: LongTextFieldProps) => (
  <Textarea
    data-testid={`long-text-${name}`}
    className="min-h-[220px] w-full resize-y font-normal"
    value={value}
    placeholder={placeholder}
    onChange={(event) => onChange(event.target.value)}
  />
);

export default LongTextField;
