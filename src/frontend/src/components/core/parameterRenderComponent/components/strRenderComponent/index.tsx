import { InputProps, StrRenderComponentType } from "../../types";
import CopyFieldAreaComponent from "../copyFieldAreaComponent";
import DropdownComponent from "../dropdownComponent";
import InputGlobalComponent from "../inputGlobalComponent";
import TextAreaComponent from "../textAreaComponent";
import WebhookFieldComponent from "../webhookFieldComponent";

export function StrRenderComponent({
  templateData,
  name,
  display_name,
  placeholder,
  ...baseInputProps
}: InputProps<string, StrRenderComponentType>) {
  const { handleOnNewValue, id, isToolMode, nodeInformationMetadata } =
    baseInputProps;

  const noOptions = !templateData.options;
  const isMultiline = templateData.multiline;
  const copyField = templateData.copy_field;
  const hasOptions = !!templateData.options;
  const isWebhook = nodeInformationMetadata?.nodeType === "webhook";

  if (noOptions) {
    if (isMultiline) {
      if (isWebhook) {
        return <WebhookFieldComponent {...baseInputProps} />;
      }

      if (copyField) {
        return <CopyFieldAreaComponent {...baseInputProps} />;
      }

      return (
        <TextAreaComponent
          {...baseInputProps}
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
      );
    }

    return (
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

  if (hasOptions) {
    return (
      <DropdownComponent
        {...baseInputProps}
        dialogInputs={templateData.dialog_inputs}
        options={templateData.options ?? []}
        optionsMetaData={templateData.options_metadata}
        combobox={templateData.combobox}
        name={templateData?.name!}
      />
    );
  }
}
