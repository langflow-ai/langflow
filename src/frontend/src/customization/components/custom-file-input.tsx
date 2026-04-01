import IOFileInput from "@/modals/IOModal/components/IOFieldView/components/file-input";
import type { IOFileInputProps } from "@/types/components";

export function CustomIOFileInput({ field, updateValue }: IOFileInputProps) {
  return <IOFileInput field={field} updateValue={updateValue} />;
}

export default CustomIOFileInput;
