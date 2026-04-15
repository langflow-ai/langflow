import { useCallback, useEffect, useMemo, useRef } from "react";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import type { GlobalVariable } from "./types";

// Custom hook for managing global variable value existence
export const useGlobalVariableValue = (
  value: string,
  globalVariables: GlobalVariable[],
) => {
  return useMemo(() => {
    return (
      globalVariables?.some((variable) => variable.name === value) ?? false
    );
  }, [globalVariables, value]);
};

// Custom hook for managing unavailable fields
export const useUnavailableField = (
  displayName: string | undefined,
  value: string,
) => {
  const unavailableFields = useGlobalVariablesStore(
    (state) => state.unavailableFields,
  );

  return useMemo(() => {
    if (
      displayName &&
      unavailableFields &&
      Object.keys(unavailableFields).includes(displayName) &&
      value === ""
    ) {
      return unavailableFields[displayName];
    }
    return null;
  }, [unavailableFields, displayName, value]);
};

// Custom hook for handling initial load logic
export const useInitialLoad = (
  disabled: boolean,
  loadFromDb: boolean,
  globalVariables: GlobalVariable[],
  valueExists: boolean,
  unavailableField: string | null,
  handleOnNewValue: (
    value: { value: string; load_from_db: boolean },
    options?: { skipSnapshot: boolean },
  ) => void,
) => {
  const initialLoadCompleted = useRef(false);
  const handleOnNewValueRef = useRef(handleOnNewValue);

  // Keep the latest handleOnNewValue reference
  handleOnNewValueRef.current = handleOnNewValue;

  // Handle database loading when value doesn't exist
  useEffect(() => {
    if (disabled || !loadFromDb || !globalVariables.length || valueExists) {
      return;
    }

    handleOnNewValueRef.current(
      { value: "", load_from_db: false },
      { skipSnapshot: true },
    );
  }, [disabled, loadFromDb, globalVariables.length, valueExists]);

  // Handle unavailable field initialization
  useEffect(() => {
    if (initialLoadCompleted.current || disabled || unavailableField === null) {
      return;
    }

    handleOnNewValueRef.current(
      { value: unavailableField, load_from_db: true },
      { skipSnapshot: true },
    );

    initialLoadCompleted.current = true;
  }, [unavailableField, disabled]);
};
