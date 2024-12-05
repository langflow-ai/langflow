import { InputProps, StrRenderComponentType } from "../../types";
import DropdownComponent from "../dropdownComponent";
import InputGlobalComponent from "../inputGlobalComponent";
import TextAreaComponent from "../textAreaComponent";

export function StrRenderComponent({
  templateData,
  name,
  display_name,
  placeholder,
  ...baseInputProps
}: InputProps<string, StrRenderComponentType>) {
  const { handleOnNewValue, id, isToolMode } = baseInputProps;

  if (!templateData.options) {
    return templateData.multiline ? (
      <TextAreaComponent
        {...baseInputProps}
        // password={templateData.password}
        updateVisibility={() => {
          if (templateData.password !== undefined) {
            handleOnNewValue(
              { password: !templateData.password },
              { skipSnapshot: true },
            );
          }
        }}
        id={`textarea_${id}`}
        isToolMode={isToolMode}
      />
    ) : (
      <InputGlobalComponent
        {...baseInputProps}
        password={templateData.password}
        load_from_db={templateData.load_from_db}
        placeholder={placeholder}
        display_name={display_name}
        id={`input-${name}`}
        isToolMode={isToolMode}
      />
    );
  }

  if (!!templateData.options) {
    return (
      <DropdownComponent
        {...baseInputProps}
        options={templateData.options}
        combobox={templateData.combobox}
        name={templateData?.name!}
      />
    );
  }
}
