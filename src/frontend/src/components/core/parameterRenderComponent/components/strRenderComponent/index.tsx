import { useCallback } from "react";
import { ReferenceInput } from "@/components/core/referenceInput";
import { parseReferences } from "@/utils/referenceParser";
import type { InputProps, StrRenderComponentType } from "../../types";
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
  nodeId,
  nodeClass,
  handleNodeClass,
  ...baseInputProps
}: InputProps<string, StrRenderComponentType>) {
  const { handleOnNewValue, id, isToolMode, nodeInformationMetadata, value } =
    baseInputProps;

  const noOptions = !templateData.options;
  const isMultiline = templateData.multiline;
  const copyField = templateData.copy_field;
  const hasOptions = !!templateData.options;
  const isWebhook = nodeInformationMetadata?.nodeType === "webhook";

  // Check if this field supports references (has_references is defined, not undefined)
  const supportsReferences = templateData.has_references !== undefined;

  // Helper to extract string value from various input formats
  const extractStringValue = useCallback((newValue: unknown): string | null => {
    if (typeof newValue === "string") return newValue;
    if (
      typeof newValue === "object" &&
      newValue !== null &&
      "value" in newValue &&
      typeof (newValue as { value: unknown }).value === "string"
    ) {
      return (newValue as { value: string }).value;
    }
    return null;
  }, []);

  // Helper to update has_references in nodeClass template
  const updateHasReferences = useCallback(
    (hasRefs: boolean) => {
      if (templateData.has_references !== hasRefs && handleNodeClass) {
        handleNodeClass({
          ...nodeClass,
          template: {
            ...nodeClass.template,
            [name]: {
              ...templateData,
              has_references: hasRefs,
            },
          },
        });
      }
    },
    [templateData, handleNodeClass, nodeClass, name],
  );

  // Wrap handleOnNewValue to also update has_references when value changes
  const handleOnNewValueWithReferences = useCallback(
    (newValue: any, options?: { skipSnapshot?: boolean }) => {
      if (supportsReferences) {
        const stringValue = extractStringValue(newValue);
        if (stringValue !== null) {
          const refs = parseReferences(stringValue);
          updateHasReferences(refs.length > 0);
        }
      }
      handleOnNewValue(newValue, options);
    },
    [
      supportsReferences,
      extractStringValue,
      updateHasReferences,
      handleOnNewValue,
    ],
  );

  // Callback for ReferenceInput onChange
  const handleReferenceInputChange = useCallback(
    (newValue: string, hasRefs: boolean) => {
      updateHasReferences(hasRefs);
      handleOnNewValue({ value: newValue, has_references: hasRefs });
    },
    [updateHasReferences, handleOnNewValue],
  );

  // Callback for InputGlobalComponent inside ReferenceInput
  const handleInputGlobalNewValue = useCallback(
    (
      onChange: (
        e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
      ) => void,
    ) => {
      return (newValue: unknown, _options?: { skipSnapshot?: boolean }) => {
        const valueStr = extractStringValue(newValue);
        if (valueStr === null) return;

        const syntheticEvent = {
          target: { value: valueStr, selectionStart: valueStr.length },
        } as React.ChangeEvent<HTMLInputElement>;
        onChange(syntheticEvent);
      };
    },
    [extractStringValue],
  );

  // Create modified baseInputProps with the wrapped handler
  const modifiedBaseInputProps = supportsReferences
    ? { ...baseInputProps, handleOnNewValue: handleOnNewValueWithReferences }
    : baseInputProps;

  if (noOptions) {
    if (isMultiline) {
      if (isWebhook) {
        return <WebhookFieldComponent {...modifiedBaseInputProps} />;
      }

      if (copyField) {
        return <CopyFieldAreaComponent {...modifiedBaseInputProps} />;
      }

      // For multiline input with reference support, wrap with ReferenceInput
      if (supportsReferences && nodeId) {
        return (
          <ReferenceInput
            nodeId={nodeId}
            value={(value as string) ?? ""}
            onChange={handleReferenceInputChange}
          >
            {({
              value: inputValue,
              actualValue: storedValue,
              onChange,
              onKeyDown,
            }) => (
              <TextAreaComponent
                {...baseInputProps}
                value={inputValue}
                nodeId={nodeId}
                onKeyDown={onKeyDown}
                handleOnNewValue={(newVal: any) => {
                  // Extract the actual value and cursor position
                  const extractedValue =
                    typeof newVal === "object" &&
                    newVal !== null &&
                    "value" in newVal
                      ? newVal.value
                      : newVal;
                  const cursorPosition =
                    typeof newVal === "object" &&
                    newVal !== null &&
                    "cursorPosition" in newVal
                      ? newVal.cursorPosition
                      : (extractedValue as string).length;
                  // Simulate a change event for ReferenceInput
                  // Include tagName for proper element detection
                  const syntheticEvent = {
                    target: {
                      value: extractedValue as string,
                      selectionStart: cursorPosition,
                      tagName: "TEXTAREA",
                    },
                  } as React.ChangeEvent<HTMLTextAreaElement>;
                  onChange(syntheticEvent);
                }}
                updateVisibility={() => {
                  if (templateData.password !== undefined) {
                    handleOnNewValueWithReferences(
                      { password: !templateData.password },
                      { skipSnapshot: true },
                    );
                  }
                }}
                id={`textarea_${id}`}
                isToolMode={isToolMode}
              />
            )}
          </ReferenceInput>
        );
      }

      return (
        <TextAreaComponent
          {...modifiedBaseInputProps}
          updateVisibility={() => {
            if (templateData.password !== undefined) {
              handleOnNewValueWithReferences(
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

    // For single-line input with reference support, wrap with ReferenceInput
    if (supportsReferences && nodeId) {
      return (
        <ReferenceInput
          nodeId={nodeId}
          value={(value as string) ?? ""}
          onChange={handleReferenceInputChange}
        >
          {({ value: inputValue, onChange, onKeyDown }) => (
            <div onKeyDown={onKeyDown}>
              <InputGlobalComponent
                {...baseInputProps}
                value={inputValue}
                handleOnNewValue={handleInputGlobalNewValue(onChange)}
                password={templateData.password}
                load_from_db={templateData.load_from_db}
                placeholder={placeholder}
                display_name={display_name}
                id={`input-${name}`}
                isToolMode={isToolMode}
              />
            </div>
          )}
        </ReferenceInput>
      );
    }

    return (
      <InputGlobalComponent
        {...modifiedBaseInputProps}
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
        {...modifiedBaseInputProps}
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
