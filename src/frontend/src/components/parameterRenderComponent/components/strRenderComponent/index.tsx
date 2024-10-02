import InputGlobalComponent from "../inputGlobalComponent";
import MultiselectComponent from "../../../multiselectComponent";
import TextAreaComponent from "../textAreaComponent";
import { InputProps, StrRenderComponentType } from "../../types";
import DropdownComponent from "../dropdownComponent";

export function StrRenderComponent({
  templateData,
  name,
  ...baseInputProps
}: InputProps<string, StrRenderComponentType>) {
  const onChange = (value: any, dbValue?: boolean, skipSnapshot?: boolean) => {
    handleOnNewValue({ value, load_from_db: dbValue }, { skipSnapshot });
  };

  const { handleOnNewValue, id, disabled, editNode,value } = baseInputProps;

  if (!templateData.options) {
    return templateData.multiline ? (
      <TextAreaComponent
        {...baseInputProps}
        password={templateData.password}
        updateVisibility={() => {
          if (templateData.password !== undefined) {
            handleOnNewValue(
              { password: !templateData.password },
              { skipSnapshot: true },
            );
          }
        }}
        id={`textarea_${id}`}
      />
    ) : (
      <InputGlobalComponent
        disabled={disabled}
        editNode={editNode}
        onChange={onChange}
        name={name}
        data={templateData}
      />
    );
  }

  if (!!templateData.options && !!templateData?.list) {
    return (
      <MultiselectComponent
        editNode={editNode}
        disabled={disabled}
        options={
          (Array.isArray(templateData.options)
            ? templateData.options
            : [templateData.options]) || []
        }
        combobox={templateData.combobox}
        value={
          (Array.isArray(templateData.value)
            ? templateData.value
            : [templateData.value]) || []
        }
        id={`multiselect_${id}`}
        onSelect={onChange}
      />
    );
  }

  if (!!templateData.options) {
    return (
      <DropdownComponent
        {...baseInputProps}
        options={templateData.options}
        combobox={templateData.combobox}
      />
    );
  }
}
