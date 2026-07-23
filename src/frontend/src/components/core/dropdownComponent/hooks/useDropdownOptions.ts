import Fuse from "fuse.js";
import { type ChangeEvent, useEffect, useState } from "react";

/**
 * Options / filtering state for the dropdown: the open flags, the
 * filtered options+metadata pair, the custom combobox value and the
 * four synchronization effects, moved verbatim from the component.
 * Effect order and dependency arrays are intentionally identical to
 * the original inline code.
 */
export function useDropdownOptions({
  value,
  options,
  validOptions,
  optionsMetaData,
  combobox,
  disabled,
  hasChildren,
  onSelect,
}: {
  value: string;
  options: string[];
  validOptions: string[];
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  optionsMetaData: Record<string, any>[] | undefined;
  combobox?: boolean;
  disabled?: boolean;
  hasChildren: boolean;
  onSelect: (
    value: string,
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    dbValue?: any,
    skipSnapshot?: boolean,
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    metadata?: any,
  ) => void;
}) {
  // Initialize state and refs
  const [open, setOpen] = useState(hasChildren ? true : false);
  const [openDialog, setOpenDialog] = useState(false);
  const [waitingForResponse, setWaitingForResponse] = useState(false);
  const [customValue, setCustomValue] = useState("");

  const [filteredOptions, setFilteredOptions] = useState(() => {
    // Include the current value in filteredOptions if it's a custom value not in validOptions
    if (value && !validOptions.includes(value) && combobox) {
      return [...validOptions, value];
    }
    return validOptions;
  });
  const [filteredMetadata, setFilteredMetadata] = useState(optionsMetaData);
  const [refreshOptions, setRefreshOptions] = useState(false);
  const [pendingSelect, setPendingSelect] = useState<string | null>(null);

  // Reset the value when options are loaded and the current value is not among them.
  // This is in a useEffect (not useMemo) to avoid calling setState during render.
  // When options is empty, it means options are still loading, so we preserve the saved value.
  useEffect(() => {
    if (
      options.length > 0 &&
      !options.includes(value) &&
      !filteredOptions.includes(value)
    ) {
      if (value) onSelect("", undefined, true);
    }
  }, [value, options, filteredOptions]);

  const fuse = new Fuse(validOptions, { keys: ["name", "value"] });

  const searchRoleByTerm = async (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setCustomValue(value);

    if (!value) {
      // If search is cleared, show all options
      // Preserve any custom values that were in filteredOptions
      const customValuesInFiltered = filteredOptions.filter(
        (option) => !validOptions.includes(option) && option === customValue,
      );
      setFilteredOptions([...validOptions, ...customValuesInFiltered]);
      setFilteredMetadata(optionsMetaData);
      return;
    }

    // Search existing options
    const searchValues = fuse.search(value);
    let filtered = searchValues.map((search) => search.item);

    // If the search value exactly matches one of the custom options, include it
    const customOptions = filteredOptions.filter(
      (option) => !validOptions.includes(option),
    );
    const matchingCustomOption = customOptions.find(
      (option) => option.toLowerCase() === value.toLowerCase(),
    );

    // Include matching custom options or allow adding the current search if combobox is true
    if (matchingCustomOption && !filtered.includes(matchingCustomOption)) {
      filtered.push(matchingCustomOption);
    } else if (
      combobox &&
      value &&
      !filtered.some((opt) => opt.toLowerCase() === value.toLowerCase())
    ) {
      // If combobox is enabled and we're typing a new value, include it in the filtered list
      filtered = [value, ...filtered];
    }

    // Update filteredOptions with the search results
    setFilteredOptions(filtered);

    // Create a new metadata array that directly maps to filtered options
    if (optionsMetaData) {
      // Create a map of option -> metadata for quick lookup
      // biome-ignore lint/suspicious/noExplicitAny: legacy
      const metadataMap: Record<string, any> = {};
      validOptions.forEach((option, index) => {
        if (optionsMetaData[index]) {
          metadataMap[option] = optionsMetaData[index];
        }
      });

      // Map each filtered option to its metadata (or undefined for custom values)
      const newMetadata = filtered.map((option) => metadataMap[option]);
      setFilteredMetadata(newMetadata);
    } else {
      setFilteredMetadata(undefined);
    }
  };

  // Auto-select a newly created option (e.g. knowledge base) once it appears in the options list
  useEffect(() => {
    if (pendingSelect && options.includes(pendingSelect)) {
      onSelect(pendingSelect);
      setPendingSelect(null);
    }
  }, [options, pendingSelect, onSelect]);

  // Effects
  useEffect(() => {
    if (disabled && value !== "") {
      onSelect("", undefined, true);
    }
  }, [disabled]);

  useEffect(() => {
    if (open) {
      // Check if filteredOptions contains any custom values not in validOptions
      const customValuesInFiltered = filteredOptions.filter(
        (option) => !validOptions.includes(option) && option === customValue,
      );

      // If there are custom values, preserve them when resetting filtered options
      if (customValuesInFiltered.length > 0 && combobox) {
        setFilteredOptions([...validOptions, ...customValuesInFiltered]);

        // Reset filteredMetadata to match the new filteredOptions
        if (optionsMetaData) {
          // biome-ignore lint/suspicious/noExplicitAny: legacy
          const metadataMap: Record<string, any> = {};
          validOptions.forEach((option, index) => {
            if (optionsMetaData[index]) {
              metadataMap[option] = optionsMetaData[index];
            }
          });

          const newMetadata = [...validOptions, ...customValuesInFiltered].map(
            (option) => metadataMap[option],
          );
          setFilteredMetadata(newMetadata);
        }
      } else {
        setFilteredOptions(validOptions);
        setFilteredMetadata(optionsMetaData);
      }
    }
    if (
      !combobox &&
      value &&
      validOptions.length > 0 &&
      !validOptions.includes(value)
    ) {
      onSelect("", undefined, true);
    }
  }, [open, validOptions]);

  return {
    open,
    setOpen,
    openDialog,
    setOpenDialog,
    waitingForResponse,
    setWaitingForResponse,
    customValue,
    filteredOptions,
    setFilteredOptions,
    filteredMetadata,
    refreshOptions,
    setRefreshOptions,
    setPendingSelect,
    searchRoleByTerm,
  };
}
