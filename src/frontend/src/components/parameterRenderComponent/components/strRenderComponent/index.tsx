import InputGlobalComponent from "../inputGlobalComponent";
import MultiselectComponent from "../multiselectComponent";
import TextAreaComponent from "../textAreaComponent";
import { InputProps, StrRenderComponentType } from "../../types";
import DropdownComponent from "../dropdownComponent";

export function StrRenderComponent({
  templateData,
  name,
  ...baseInputProps
}: InputProps<string, StrRenderComponentType>) {
  const { handleOnNewValue, id, disabled, editNode, value } = baseInputProps;

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
        {...baseInputProps}
        password={templateData.password}
        load_from_db={templateData.load_from_db}
        id={"input-" + name}
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
