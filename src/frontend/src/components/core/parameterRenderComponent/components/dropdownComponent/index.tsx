import Dropdown from "../../../dropdownComponent";
import type { DropDownComponentType, InputProps } from "../../types";
import ToggleShadComponent from "../toggleShadComponent";

export default function DropdownComponent({
  id,
  value,
  editNode,
  handleOnNewValue,
  disabled,
  combobox,
  options,
  name,
  dialogInputs,
  optionsMetaData,
  placeholder,
  nodeClass,
  nodeId,
  handleNodeClass,
  toggle,
  toggleValue,
  toggleDisable,
  hasRefreshButton,
  ...baseInputProps
}: InputProps<string, DropDownComponentType>) {
  const onChange = (value: any, dbValue?: boolean, skipSnapshot?: boolean) => {
    handleOnNewValue({ value, load_from_db: dbValue }, { skipSnapshot });
  };

  return (
    <div className="flex w-full items-center gap-4">
      <Dropdown
        disabled={disabled || toggleValue === false}
        editNode={editNode}
        toggle={toggle}
        options={options}
        nodeId={nodeId}
        nodeClass={nodeClass}
        handleNodeClass={handleNodeClass}
        optionsMetaData={optionsMetaData}
        onSelect={onChange}
        placeholder={placeholder}
        combobox={combobox}
        value={value || (toggleValue === false && toggle ? options[0] : "")}
        id={`dropdown_${id}`}
        name={name}
        dialogInputs={dialogInputs}
        handleOnNewValue={handleOnNewValue}
        hasRefreshButton={hasRefreshButton}
        {...baseInputProps}
      />
      {toggle && toggleDisable !== true ? (
        <ToggleShadComponent
          value={toggleValue ?? true}
          handleOnNewValue={(data) => {
            handleOnNewValue({
              value: data.value === true ? options[0] : null,
              toggle_value: data.value,
            });
          }}
          editNode={editNode}
          id={`toggle_dropdown_${id}`}
          disabled={disabled}
        />
      ) : (
        <></>
      )}
    </div>
  );
}
