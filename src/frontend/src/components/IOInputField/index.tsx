import { Textarea } from "../ui/textarea";
import InputFileComponent from "../inputFileComponent";
import { IOInputProps } from "../../types/components";

export default function IOInputField({
  inputType,
  value,
  onChange,
  styleClasses,
  placeholder,
}: IOInputProps): JSX.Element | undefined {
   switch (inputType) {
    case "TextInput":
        return (
            <Textarea
              className={styleClasses}
              placeholder={placeholder}
              value={value}
              onChange={onChange}
            />
        );
  }
}
