import { IOInputProps } from "../../types/components";
import IOFileInput from "../IOInputs/FileInput";
import { Textarea } from "../ui/textarea";

export default function IOInputField({
  inputType,
  field,
  updateValue,
}: IOInputProps): JSX.Element | undefined {
  function handleInputType() {
    switch (inputType) {
      case "TextInput":
        return (
          <Textarea
            className="custom-scroll"
            placeholder={"Enter text..."}
            value={field.value}
            onChange={updateValue}
          />
        );
      case "fileLoader":
        return <IOFileInput field={field} updateValue={updateValue} />;

      default:
        return (
          <Textarea
            className="custom-scroll"
            placeholder={"Enter text..."}
            value={field.value}
            onChange={updateValue}
          />
        );
    }
  }
  return <div className="h-full">{handleInputType()}</div>;
}
