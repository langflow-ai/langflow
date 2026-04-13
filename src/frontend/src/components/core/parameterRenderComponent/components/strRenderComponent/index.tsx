import { useEffect } from "react";
import type { InputProps, StrRenderComponentType } from "../../types";
import CopyFieldAreaComponent from "../copyFieldAreaComponent";
import DropdownComponent from "../dropdownComponent";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import InputComponent from "../inputComponent";
import InputGlobalComponent from "../inputGlobalComponent";
import TextAreaComponent from "../textAreaComponent";
import WebhookFieldComponent from "../webhookFieldComponent";

export function StrRenderComponent({
  templateData,
  name,
  display_name,
  placeholder,
  nodeId,
  nodeClass,
  handleNodeClass,
  ...baseInputProps
}: InputProps<string, StrRenderComponentType>) {
  const { handleOnNewValue, id, isToolMode, nodeInformationMetadata } =
    baseInputProps;

  const allowGlobalVariables =
    templateData.type === "SecretStr" || templateData.password === true;

  useEffect(() => {
    if (!allowGlobalVariables && templateData.load_from_db) {
      handleOnNewValue({ load_from_db: false }, { skipSnapshot: true });
    }
  }, [allowGlobalVariables, templateData.load_from_db, handleOnNewValue]);

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

    if (allowGlobalVariables) {
      return (
        <InputGlobalComponent
          {...baseInputProps}
          password={templateData.password}
          load_from_db={templateData.load_from_db}
          placeholder={placeholder}
          display_name={display_name}
          id={`input-${name}`}
          isToolMode={isToolMode}
          hasRefreshButton={!!templateData.refresh_button}
        />
      );
    }

    return (
      <InputComponent
        nodeStyle
        placeholder={getPlaceholder(!!baseInputProps.disabled, placeholder)}
        id={`input-${name}`}
        editNode={baseInputProps.editNode}
        disabled={baseInputProps.disabled}
        password={templateData.password ?? false}
        value={baseInputProps.value ?? ""}
        onChange={(inputValue: string, skipSnapshot?: boolean) => {
          handleOnNewValue(
            { value: inputValue, load_from_db: false },
            { skipSnapshot },
          );
        }}
        isToolMode={isToolMode}
        hasRefreshButton={!!templateData.refresh_button}
        inspectionPanel={baseInputProps.inspectionPanel}
      />
    );
  }

  if (hasOptions) {
    return (
      <DropdownComponent
        {...baseInputProps}
        dialogInputs={templateData.dialog_inputs}
        externalOptions={templateData.external_options}
        options={templateData.options ?? []}
        nodeId={nodeId}
        nodeClass={nodeClass}
        placeholder={placeholder}
        handleNodeClass={handleNodeClass}
        optionsMetaData={templateData.options_metadata}
        combobox={templateData.combobox}
        name={templateData?.name!}
        toggle={templateData.toggle}
        toggleValue={templateData.toggle_value}
        toggleDisable={templateData.toggle_disable}
        hasRefreshButton={templateData.refresh_button}
      />
    );
  }
}
