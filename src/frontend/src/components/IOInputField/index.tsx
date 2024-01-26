import { IOInputProps } from "../../types/components";
import { Textarea } from "../ui/textarea";

export default function IOInputField({
  inputType,
  value,
  updateValue,
}: IOInputProps): JSX.Element | undefined {
  switch (inputType) {
    case "TextInput":
      return (
        <Textarea
          className="custom-scroll"
          placeholder={"Enter text..."}
          value={value}
          onChange={updateValue}
        />
      );
  }
}
