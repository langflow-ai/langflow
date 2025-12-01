/**
 * GenesisPromptDropdown - A wrapper around the core Dropdown component
 * that provides Genesis Prompt-specific display formatting.
 *
 * This component transforms prompt options to show:
 * - Prompt name as the display text (instead of prompt ID)
 * - Prompt ID shown in tooltip on hover
 */

import { useMemo } from "react";
import Dropdown from "../dropdownComponent";
import type { DropDownComponent } from "../../../types/components";
import type { BaseInputProps } from "../parameterRenderComponent/types";

export type GenesisPromptDropdownProps = BaseInputProps &
  DropDownComponent & {
    // Genesis Prompt specific - metadata should contain 'name' field for prompt name
  };

// Map to store display name -> original ID mapping
const displayToIdMap = new Map<string, string>();

export default function GenesisPromptDropdown({
  options,
  optionsMetaData,
  value,
  onSelect,
  ...restProps
}: GenesisPromptDropdownProps): JSX.Element {
  // Transform options to show prompt name instead of ID
  const { transformedOptions, transformedMetadata, idToDisplayMap } = useMemo(() => {
    displayToIdMap.clear();
    
    if (!optionsMetaData || optionsMetaData.length === 0) {
      return { 
        transformedOptions: options, 
        transformedMetadata: optionsMetaData,
        idToDisplayMap: new Map<string, string>()
      };
    }

    const newOptions: string[] = [];
    const newMetadata: any[] = [];
    const idToDisplay = new Map<string, string>();

    options.forEach((option, index) => {
      const metadata = optionsMetaData[index];
      const promptName = metadata?.name;

      if (promptName) {
        // Use prompt name as display, keep ID in tooltip metadata
        newOptions.push(promptName);
        newMetadata.push({
          ...metadata,
          name: undefined, // Remove name from metadata so it doesn't show twice
          id: option, // Add ID to show in tooltip
        });
        displayToIdMap.set(promptName, option);
        idToDisplay.set(option, promptName);
      } else {
        newOptions.push(option);
        newMetadata.push(metadata);
        idToDisplay.set(option, option);
      }
    });

    return {
      transformedOptions: newOptions,
      transformedMetadata: newMetadata,
      idToDisplayMap: idToDisplay,
    };
  }, [options, optionsMetaData]);

  // Transform the current value to display name
  const displayValue = useMemo(() => {
    if (!value) return value;
    return idToDisplayMap.get(value) || value;
  }, [value, idToDisplayMap]);

  // Wrap onSelect to map display name back to original ID
  const handleSelect = (
    selectedValue: string,
    dbValue?: boolean,
    snapshot?: boolean
  ) => {
    const originalId = displayToIdMap.get(selectedValue) || selectedValue;
    onSelect(originalId, dbValue, snapshot);
  };

  return (
    <Dropdown
      {...restProps}
      options={transformedOptions}
      optionsMetaData={transformedMetadata}
      value={displayValue}
      onSelect={handleSelect}
    />
  );
}
