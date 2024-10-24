import Dropdown from "../../../dropdownComponent";
import { DropDownComponentType, InputProps } from "../../types";

export default function DropdownComponent({
  id,
  value,
  editNode,
  handleOnNewValue,
  disabled,
  combobox,
  options,
  name,
}: InputProps<string, DropDownComponentType>) {
  const onChange = (value: any, dbValue?: boolean, skipSnapshot?: boolean) => {
    handleOnNewValue({ value, load_from_db: dbValue }, { skipSnapshot });
  };
  return (
    <Dropdown
      disabled={disabled}
      editNode={editNode}
      options={options}
      onSelect={onChange}
      combobox={combobox}
      value={value || ""}
      id={`dropdown_${id}`}
      name={name}
    />
  );
}
